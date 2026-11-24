from datetime import datetime, timedelta

from tests.support import ApiTestCase

from app.database import SessionLocal, engine
from app.models import ActivityLog, AssistantConversation, AssistantMessage, Document, User


class AdminApiTests(ApiTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ActivityLog.__table__.create(bind=engine, checkfirst=True)

    def setUp(self):
        super().setUp()
        # ApiTestCase shares one disposable database across methods in a process.
        # Clear only these test tables so each admin test starts with isolated data.
        with SessionLocal() as session:
            session.query(AssistantMessage).delete(synchronize_session=False)
            session.query(AssistantConversation).delete(synchronize_session=False)
            session.query(Document).delete(synchronize_session=False)
            session.query(ActivityLog).delete(synchronize_session=False)
            session.query(User).delete(synchronize_session=False)
            session.commit()

    def admin_account(self):
        _, token = self.create_account("Administrator")
        response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        user_id = response.json()["id"]
        with SessionLocal() as session:
            user = session.get(User, user_id)
            user.is_admin = True
            session.commit()
        return user_id, token

    def auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    def add_event(self, user_id, action, created_at=None, metadata=None):
        with SessionLocal() as session:
            event = ActivityLog(
                user_id=user_id,
                action=action,
                entity_type="test",
                metadata_json=metadata or {},
                created_at=created_at or datetime.utcnow(),
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event.id

    def test_admin_routes_require_authentication_and_admin_role(self):
        unauthenticated = self.client.get("/api/admin/stats")
        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.text)

        _, token = self.create_account("Regular User")
        forbidden = self.client.get("/api/admin/stats", headers=self.auth(token))
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

    def test_admin_can_read_stats_with_activity_counts_and_history_note(self):
        user_id, token = self.admin_account()
        with SessionLocal() as session:
            session.add(Document(
                owner_id=user_id,
                original_name="private.txt",
                stored_name="test-admin-stats-file.txt",
                content_type="text/plain",
                size=10,
            ))
            session.commit()

        self.add_event(user_id, "pdf.info")
        self.add_event(user_id, "pdf.merge")
        self.add_event(user_id, "translation.text")
        self.add_event(user_id, "assistant.message")
        self.add_event(user_id, "assistant.summarize")

        response = self.client.get("/api/admin/stats", headers=self.auth(token))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {
                "total_users": 1,
                "total_documents": 1,
                "total_pdf_operations": 2,
                "total_translations": 1,
                "total_ai_usage": 2,
                "historical_activity_limited": True,
                "historical_activity_note": "PDF, translation, and AI totals include tracked activity only since activity logging was enabled.",
            },
        )

    def test_activity_is_paginated_newest_first_and_omits_metadata(self):
        user_id, token = self.admin_account()
        base_time = datetime.utcnow()
        self.add_event(user_id, "pdf.info", base_time, {"prompt": "private content"})
        newest_id = self.add_event(user_id, "translation.text", base_time + timedelta(seconds=1), {"secret": "private-token"})
        headers = self.auth(token)

        page_one = self.client.get("/api/admin/activity?limit=1&offset=0", headers=headers)
        page_two = self.client.get("/api/admin/activity?limit=1&offset=1", headers=headers)
        self.assertEqual(page_one.status_code, 200, page_one.text)
        self.assertEqual(page_two.status_code, 200, page_two.text)
        body = page_one.json()
        self.assertEqual(body["total"], 4)  # signup, login, and the two seeded events
        self.assertEqual(body["items"][0]["id"], newest_id)
        self.assertEqual(body["items"][0]["user_id"], user_id)
        self.assertIn("user_email", body["items"][0])
        self.assertEqual(set(body["items"][0]), {"id", "user_id", "user_email", "action", "entity_type", "created_at"})
        self.assertEqual(body["items"][0]["action"], "translation.text")
        self.assertEqual(page_two.json()["items"][0]["action"], "pdf.info")
        self.assertNotIn("private content", page_one.text)
        self.assertNotIn("private-token", page_one.text)

    def test_user_listing_is_paginated_and_excludes_password_hash(self):
        _, admin_token = self.admin_account()
        self.create_account("Second User")
        response = self.client.get("/api/admin/users?limit=1&offset=0", headers=self.auth(admin_token))
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(set(body["items"][0]), {"id", "email"})
        self.assertNotIn("password_hash", response.text)
        self.assertNotIn("access_token", response.text)

    def test_user_history_empty_and_missing_user_behavior(self):
        _, token = self.admin_account()
        with SessionLocal() as session:
            user_without_activity = User(
                name="No Activity",
                email="no-activity@example.com",
                password_hash="test-only-hash",
            )
            session.add(user_without_activity)
            session.commit()
            session.refresh(user_without_activity)
            empty_user_id = user_without_activity.id

        empty_response = self.client.get(
            f"/api/admin/users/{empty_user_id}/activity", headers=self.auth(token)
        )
        missing_response = self.client.get(
            "/api/admin/users/999999/activity", headers=self.auth(token)
        )
        self.assertEqual(empty_response.status_code, 200, empty_response.text)
        self.assertEqual(empty_response.json()["items"], [])
        self.assertEqual(empty_response.json()["total"], 0)
        self.assertEqual(missing_response.status_code, 404, missing_response.text)


if __name__ == "__main__":
    import unittest

    unittest.main()
