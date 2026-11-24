import json
import io
import os
from unittest.mock import patch

from pypdf import PdfWriter
from tests.support import ApiTestCase

from app.activity import record_activity
from app.database import SessionLocal, engine
from app.models import ActivityLog, AssistantConversation, AssistantMessage


class FakeProviderStream:
    def __init__(self, lines, status_code=200):
        self.lines = lines
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeProviderResponse:
    status_code = 200
    text = ""

    def json(self):
        return {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "test-tool-call",
                        "function": {"name": "get_document_info", "arguments": "{}"},
                    }],
                },
            }]
        }


class FakeProviderClient:
    def __init__(self, lines):
        self.lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def stream(self, *args, **kwargs):
        return FakeProviderStream(self.lines)

    async def post(self, *args, **kwargs):
        return FakeProviderResponse()


class ActivityLoggingTests(ApiTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ActivityLog.__table__.create(bind=engine, checkfirst=True)

    def test_auth_events_use_authenticated_account_id(self):
        _, token = self.create_account()
        response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        user_id = response.json()["id"]

        with SessionLocal() as session:
            events = session.query(ActivityLog).filter_by(user_id=user_id).all()
            actions = {event.action for event in events}
            self.assertEqual(actions, {"auth.signup", "auth.login"})
            self.assertTrue(all(event.user_id == user_id for event in events))
            self.assertTrue(all(event.entity_id == user_id for event in events))

    def test_helper_filters_metadata_and_stores_event(self):
        _, token = self.create_account()
        user_id = self.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        ).json()["id"]

        logged = record_activity(
            user_id,
            "assistant.message",
            "assistant_conversation",
            92,
            {
                "mode": "stream",
                "language": "en",
                "attachment_count": 2,
                "prompt": "private prompt",
                "response": "private response",
                "filename": "private.pdf",
                "tool_options": {"secret": "value"},
            },
        )
        self.assertTrue(logged)

        with SessionLocal() as session:
            event = session.query(ActivityLog).filter_by(
                user_id=user_id, action="assistant.message", entity_id=92
            ).one()
            self.assertEqual(
                event.metadata_json,
                {"mode": "stream", "language": "en", "attachment_count": 2},
            )
            serialized = json.dumps(event.metadata_json).lower()
            for private_value in ("private prompt", "private response", "private.pdf", "secret"):
                self.assertNotIn(private_value, serialized)

    def test_logging_failure_does_not_change_successful_signup_response(self):
        with patch("app.activity.SessionLocal", side_effect=RuntimeError("database unavailable")):
            response = self.client.post(
                "/api/auth/signup",
                json={
                    "name": "Logger Failure User",
                    "email": "logger-failure@example.com",
                    "password": "StrongPass123",
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(set(response.json()), {"access_token", "token_type", "user"})

    def activity_actions(self, user_id):
        with SessionLocal() as session:
            return [
                event.action
                for event in session.query(ActivityLog).filter_by(user_id=user_id).all()
            ]

    def user_id_for(self, token):
        response = self.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def test_document_upload_and_delete_are_logged(self):
        _, token = self.create_account()
        auth = {"Authorization": f"Bearer {token}"}
        user_id = self.user_id_for(token)
        uploaded = self.client.post(
            "/api/documents/upload",
            headers=auth,
            files={"file": ("activity-test.txt", b"Safe test content", "text/plain")},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        document_id = uploaded.json()["id"]
        self.assertEqual(self.client.delete(f"/api/documents/{document_id}", headers=auth).status_code, 200)
        with SessionLocal() as session:
            events = session.query(ActivityLog).filter_by(user_id=user_id).all()
            document_events = {(event.action, event.entity_id) for event in events if event.action.startswith("document.")}
        self.assertEqual(document_events, {("document.upload", document_id), ("document.delete", document_id)})

    def test_pdf_operation_is_logged(self):
        _, token = self.create_account()
        user_id = self.user_id_for(token)
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(output)
        response = self.client.post(
            "/api/pdf/info",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.pdf", output.getvalue(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("pdf.info", self.activity_actions(user_id))

    def test_translation_and_ai_chat_routes_are_logged(self):
        _, token = self.create_account()
        auth = {"Authorization": f"Bearer {token}"}
        user_id = self.user_id_for(token)
        with patch("app.routers.ai.ai_completion", return_value="Bonjour"):
            translated = self.client.post(
                "/api/ai/translate",
                headers=auth,
                json={"text": "Hello", "source_language": "en", "target_language": "fr"},
            )
        self.assertEqual(translated.status_code, 200, translated.text)
        self.assertEqual(set(translated.json()), {"translation", "source_language", "target_language", "provider"})
        with patch("app.routers.ai.ai_completion", return_value="Hello there"):
            chatted = self.client.post(
                "/api/ai/chat",
                headers=auth,
                json={"message": "Say hello", "language": "en"},
            )
        self.assertEqual(chatted.status_code, 200, chatted.text)
        self.assertEqual(set(chatted.json()), {"reply", "conversation_id", "title"})
        actions = self.activity_actions(user_id)
        self.assertEqual(actions.count("translation.text"), 1)
        self.assertEqual(actions.count("assistant.message"), 1)

    def test_humanizer_rewrites_text_and_logs_authenticated_use(self):
        _, token = self.create_account()
        auth = {"Authorization": f"Bearer {token}"}
        user_id = self.user_id_for(token)
        source_text = "The original sentence is a little awkward."
        with patch("app.routers.ai.ai_completion", return_value="The sentence now reads naturally.") as completion:
            response = self.client.post(
                "/api/ai/humanize",
                headers=auth,
                json={"text": source_text, "writing_style": "professional", "strength": 4},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["humanized_text"], "The sentence now reads naturally.")
        self.assertEqual(response.json()["engine"], "model")
        self.assertEqual(completion.call_args.args[0][1]["content"], source_text)
        self.assertIn("professional wording", completion.call_args.args[0][0]["content"])
        self.assertIn("strength 4 of 5", completion.call_args.args[0][0]["content"])
        self.assertIn("assistant.humanize", self.activity_actions(user_id))

    def assert_stream_messages_persisted(self, user_id, expected):
        with SessionLocal() as session:
            count = (
                session.query(AssistantMessage)
                .join(AssistantConversation, AssistantConversation.id == AssistantMessage.conversation_id)
                .filter(AssistantConversation.owner_id == user_id)
                .count()
            )
        self.assertEqual(count > 0, expected)

    def test_ai_stream_requires_completion_marker_before_persistence_and_logging(self):
        _, token = self.create_account()
        auth = {"Authorization": f"Bearer {token}"}
        user_id = self.user_id_for(token)
        conversation = self.client.post("/api/ai/conversations", headers=auth).json()
        token_line = 'data: {"choices":[{"delta":{"content":"partial"}}]}'

        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}), patch(
            "app.routers.ai.httpx.AsyncClient",
            return_value=FakeProviderClient([token_line]),
        ):
            premature = self.client.post(
                "/api/ai/chat/stream",
                headers=auth,
                json={"message": "test", "conversation_id": conversation["id"]},
            )
        self.assertEqual(premature.status_code, 200, premature.text)
        self.assertIn("ended before completion", premature.text)
        self.assertNotIn('"done": true', premature.text)
        self.assertNotIn("assistant.message", self.activity_actions(user_id))
        self.assert_stream_messages_persisted(user_id, False)

        complete_line = 'data: {"choices":[{"delta":{"content":"complete"}}]}'
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}), patch(
            "app.routers.ai.httpx.AsyncClient",
            return_value=FakeProviderClient([complete_line, "data: [DONE]"]),
        ):
            complete = self.client.post(
                "/api/ai/chat/stream",
                headers=auth,
                json={"message": "test", "conversation_id": conversation["id"]},
            )
        self.assertEqual(complete.status_code, 200, complete.text)
        self.assertIn('"done": true', complete.text)
        self.assertEqual(self.activity_actions(user_id).count("assistant.message"), 1)
        self.assert_stream_messages_persisted(user_id, True)

    def test_chatbot_stream_requires_completion_marker_before_persistence_and_logging(self):
        _, token = self.create_account()
        auth = {"Authorization": f"Bearer {token}"}
        user_id = self.user_id_for(token)
        conversation = self.client.post("/api/chat/conversations", headers=auth).json()
        token_line = 'data: {"choices":[{"delta":{"content":"partial"}}]}'
        payload = {"text": "test", "conversation_id": conversation["id"], "stream": True}

        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}), patch(
            "app.chatbot.routes.httpx.AsyncClient",
            return_value=FakeProviderClient([token_line]),
        ):
            premature = self.client.post("/api/chat/message", headers=auth, json=payload)
        self.assertEqual(premature.status_code, 200, premature.text)
        self.assertIn("ended before completion", premature.text)
        self.assertNotIn('"done": true', premature.text)
        self.assertNotIn("assistant.message", self.activity_actions(user_id))
        self.assert_stream_messages_persisted(user_id, False)

        complete_line = 'data: {"choices":[{"delta":{"content":"complete"}}]}'
        with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}), patch(
            "app.chatbot.routes.httpx.AsyncClient",
            return_value=FakeProviderClient([complete_line, "data: [DONE]"]),
        ):
            complete = self.client.post("/api/chat/message", headers=auth, json=payload)
        self.assertEqual(complete.status_code, 200, complete.text)
        self.assertIn('"done": true', complete.text)
        self.assertEqual(self.activity_actions(user_id).count("assistant.message"), 1)
        self.assert_stream_messages_persisted(user_id, True)


if __name__ == "__main__":
    import unittest

    unittest.main()
