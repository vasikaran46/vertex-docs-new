import base64
import asyncio
import io
from unittest.mock import patch
from PIL import Image
from pypdf import PdfReader
from tests.support import ApiTestCase

class TemplatesAndAiTests(ApiTestCase):
    def test_templates_render_with_photo_and_ai_reports_missing_provider_key(self):
        _,token=self.create_account()
        auth={"Authorization":f"Bearer {token}"}
        template_names=("resume","cover-letter","business-letter","meeting-notes","project-proposal","invoice")
        for template in template_names:
            response=self.client.post(
                "/api/templates/render",
                headers=auth,
                json={"template":template,"full_name":"A & B","summary":"A concise summary","body":"Safe <text>"},
            )
            self.assertEqual(response.status_code,200,(template,response.text))
            self.assertTrue(response.content.startswith(b"%PDF-"))
            self.assertGreaterEqual(len(PdfReader(io.BytesIO(response.content)).pages),1)

        photo=io.BytesIO()
        Image.new("RGB",(60,90),"#468").save(photo,format="PNG")
        with_photo=self.client.post("/api/templates/render",headers=auth,json={
            "template":"resume",
            "photo_data":base64.b64encode(photo.getvalue()).decode("ascii"),
        })
        self.assertEqual(with_photo.status_code,200,with_photo.text)
        invalid_photo=self.client.post("/api/templates/render",headers=auth,json={"template":"resume","photo_data":"invalid"})
        self.assertEqual(invalid_photo.status_code,400,invalid_photo.text)

        uploaded=self.client.post(
            "/api/documents/upload",
            headers=auth,
            files={"file":("brief.txt",b"Launch date: Friday. Budget: 5000 USD.","text/plain")},
        )
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        document_id=uploaded.json()["id"]
        summary=self.client.post(f"/api/ai/documents/{document_id}/summarize",headers=auth,json={"language":"tanglish"})
        self.assertEqual(summary.status_code,503,summary.text)
        self.client.delete(f"/api/documents/{document_id}",headers=auth)

    def test_long_file_translation_uses_parallel_ordered_sections(self):
        _,token=self.create_account()
        auth={"Authorization":f"Bearer {token}"}
        paragraph="This is a complete sentence from the uploaded file. "*65
        text="\n\n".join(f"Section {index}. {paragraph}" for index in range(5))
        state={"active":0,"max_active":0}

        async def fake_completion(messages):
            state["active"]+=1
            state["max_active"]=max(state["max_active"],state["active"])
            await asyncio.sleep(0.02)
            heading=messages[-1]["content"].split(".",1)[0]
            state["active"]-=1
            return f"Translated {heading}"

        with patch("app.routers.ai.ai_completion",side_effect=fake_completion) as completion:
            response=self.client.post(
                "/api/ai/translate-file",
                headers=auth,
                data={"source_language":"auto","target_language":"fr"},
                files={"file":("long.txt",text.encode("utf-8"),"text/plain")},
            )
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(completion.await_count,5)
        self.assertGreater(state["max_active"],1)
        self.assertLessEqual(state["max_active"],4)
        self.assertEqual(
            response.json()["translation"],
            "\n\n".join(f"Translated Section {index}" for index in range(5)),
        )

    def test_ai_question_generator_uses_document_text_and_validates_count(self):
        _,token=self.create_account()
        auth={"Authorization":f"Bearer {token}"}
        with patch("app.routers.ai.ai_completion",return_value="1. What is the launch date?\n\nAnswer: Friday.") as completion:
            response=self.client.post(
                "/api/ai/question-generator",
                headers=auth,
                data={"count":"1","language":"en"},
                files={"file":("brief.txt",b"The launch date is Friday.","text/plain")},
            )
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["count"],1)
        self.assertIn("launch date",response.json()["questions"])
        completion.assert_awaited_once()

        invalid=self.client.post(
            "/api/ai/question-generator",
            headers=auth,
            data={"count":"21","language":"en"},
            files={"file":("brief.txt",b"The launch date is Friday.","text/plain")},
        )
        self.assertEqual(invalid.status_code,400,invalid.text)
