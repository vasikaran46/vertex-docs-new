import io
import json
import unittest
import zipfile
from unittest.mock import patch

from docx import Document as WordDocument
from pptx import Presentation

from app import text_export, translation_quality as tq
from tests.support import ApiTestCase


class QualityHelperTests(unittest.TestCase):
    def test_script_ratio_detects_untranslated_text(self):
        self.assertGreater(tq.target_script_ratio("नमस्ते दुनिया", "hi"), 0.9)
        self.assertLess(tq.target_script_ratio("Hello world", "hi"), 0.1)
        self.assertIsNone(tq.target_script_ratio("Bonjour", "fr"))

    def test_mixed_language_leftover_triggers_a_retry(self):
        source = "வணக்கம். Please send the report tomorrow."
        half_done = "வணக்கம். Please send the report tomorrow."
        done = "नमस्ते। कृपया कल रिपोर्ट भेजें।"
        self.assertTrue(tq.needs_retry(source, half_done, "hi"))
        self.assertFalse(tq.needs_retry(source, done, "hi"))

    def test_prompt_demands_every_language_be_translated(self):
        message = tq.build_system_message("auto", "Hindi", "hi")
        self.assertIn("EVERY part", message)
        self.assertIn("Tamil and English", message)

    def test_probe_verification(self):
        self.assertTrue(tq.verify_probe("hi", "सुप्रभात। कृपया कल तक रिपोर्ट भेज दें।")[0])
        self.assertFalse(tq.verify_probe("ta", "Good morning please send report")[0])
        self.assertTrue(tq.verify_probe("fr", "Bonjour. Veuillez m'envoyer le rapport demain.")[0])
        self.assertFalse(tq.verify_probe("fr", tq.PROBE_TEXT)[0])
        self.assertFalse(tq.verify_probe("es", "")[0])
        self.assertTrue(tq.verify_probe("en", "Please send the report by tomorrow.")[0])


class ExportFormatTests(unittest.TestCase):
    TEXT = "Vanakkam\n\nவணக்கம் உலகம்\nSecond line\n\nनमस्ते"

    def test_every_supported_format_produces_a_real_file(self):
        for fmt in ("txt", "md", "html", "docx", "rtf", "pptx", "json"):
            data, media_type, name = text_export.export_text(self.TEXT, "My Doc", fmt)
            self.assertTrue(data, fmt)
            self.assertTrue(name.endswith("." + fmt), name)
        # Contents are really the supplied text
        txt, _, _ = text_export.export_text(self.TEXT, "t", "txt")
        self.assertEqual(txt.decode("utf-8"), self.TEXT)
        docx, _, _ = text_export.export_text(self.TEXT, "t", "docx")
        paragraphs = [p.text for p in WordDocument(io.BytesIO(docx)).paragraphs]
        self.assertTrue(any("வணக்கம் உலகம்" in p for p in paragraphs))
        pptx, _, _ = text_export.export_text(self.TEXT, "t", "pptx")
        slide_text = " ".join(shape.text_frame.text for slide in Presentation(io.BytesIO(pptx)).slides for shape in slide.shapes if shape.has_text_frame)
        self.assertIn("नमस्ते", slide_text)
        data, _, _ = text_export.export_text(self.TEXT, "t", "json")
        self.assertEqual(json.loads(data)["text"], self.TEXT)
        html, _, _ = text_export.export_text("a <b> & c", "t", "html")
        self.assertIn(b"a &lt;b&gt; &amp; c", html)
        rtf, _, _ = text_export.export_text("தமிழ்", "t", "rtf")
        self.assertTrue(rtf.startswith(b"{\\rtf1"))

    def test_pdf_export_of_latin_text(self):
        data, media_type, name = text_export.export_text("Hello PDF world", "Report", "pdf")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertEqual(name, "Report.pdf")

    def test_rejects_bad_input(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            text_export.export_text("x", "t", "exe")
        with self.assertRaises(HTTPException):
            text_export.export_text("   ", "t", "txt")

    def test_filename_is_sanitized(self):
        _, _, name = text_export.export_text("x", "../../etc/passwd", "txt")
        self.assertEqual(name, "passwd.txt")


class ExportAndTranslationApiTests(ApiTestCase):
    def headers(self):
        _, token = self.create_account()
        return {"Authorization": f"Bearer {token}"}

    def test_export_endpoint_streams_real_docx_and_logs_history(self):
        headers = self.headers()
        r = self.client.post("/api/export/text", headers=headers, json={"text": "Translated text", "title": "Out", "format": "docx", "source": "translation"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(r.content)))
        self.assertIn("Out.docx", r.headers["content-disposition"])
        events = self.client.get("/api/history/events", headers=headers).json()["items"]
        self.assertEqual(events[0]["action"], "Text exported")
        self.assertEqual(self.client.post("/api/export/text", headers=headers, json={"text": "x", "format": "exe"}).status_code, 400)
        self.assertEqual(self.client.post("/api/export/text", json={"text": "x", "format": "txt"}).status_code, 401)

    def test_languages_report_unavailable_without_provider(self):
        headers = self.headers()
        with patch("app.routers.translation.llm_setting", side_effect=lambda name, default="": ""):
            r = self.client.get("/api/translation/languages?probe=true", headers=headers)
        body = r.json()
        self.assertFalse(body["provider_configured"])
        self.assertEqual(len(body["languages"]), 12)
        self.assertTrue(all(item["status"] == "unavailable" for item in body["languages"]))
        self.assertEqual([i["name"] for i in body["languages"]][:3], ["English", "Tamil", "Hindi"])

    def test_language_probe_marks_languages_the_model_cannot_do_as_unavailable(self):
        headers = self.headers()

        async def fake_completion(messages):
            target = messages[0]["content"].split("into ")[1].split(".")[0]
            return {
                "Hindi": "सुप्रभात। कृपया कल तक रिपोर्ट भेज दें।",
                "French": "Bonjour. Veuillez m'envoyer le rapport demain.",
                "English": "Please send the report by tomorrow.",
            }.get(target, "Good morning please send the report")  # model cannot do other languages

        def settings(name, default=""):
            return {"LLM_API_KEY": "k", "LLM_BASE_URL": "http://x/v1", "LLM_MODEL": "probe-model"}.get(name, default)

        with patch("app.routers.translation.ai_completion", fake_completion), \
             patch("app.routers.translation.llm_setting", settings), \
             patch("app.routers.translation.llm_models", lambda: ["probe-model"]):
            r = self.client.get("/api/translation/languages?probe=true", headers=headers)
        status = {i["name"]: i["status"] for i in r.json()["languages"]}
        self.assertEqual(status["Hindi"], "available")
        self.assertEqual(status["French"], "available")
        self.assertEqual(status["English"], "available")
        self.assertEqual(status["Tamil"], "unavailable")
        self.assertEqual(status["Japanese"], "unavailable")

    def test_translate_retries_mixed_language_output_and_reports_warnings(self):
        headers = self.headers()
        calls = []

        async def fake_completion(messages):
            calls.append(messages[0]["content"])
            return "Please send the report tomorrow."  # provider ignores the target language

        with patch("app.routers.ai.ai_completion", fake_completion):
            r = self.client.post("/api/ai/translate", headers=headers, json={
                "text": "வணக்கம் நண்பர்களே. Please send the report tomorrow.",
                "source_language": "auto", "target_language": "hi"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(calls), 2)  # first pass + strict retry
        self.assertIn("IMPORTANT", calls[1])
        self.assertTrue(r.json().get("warnings"))

    def test_translate_accepts_good_mixed_language_output_without_retry(self):
        headers = self.headers()
        calls = []

        async def fake_completion(messages):
            calls.append(1)
            return "नमस्ते दोस्तों। कृपया कल रिपोर्ट भेजें।"

        with patch("app.routers.ai.ai_completion", fake_completion):
            r = self.client.post("/api/ai/translate", headers=headers, json={
                "text": "வணக்கம் நண்பர்களே. Please send the report tomorrow.",
                "source_language": "auto", "target_language": "hi"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("warnings", r.json())
        self.assertIn("नमस्ते", r.json()["translation"])


if __name__ == "__main__":
    unittest.main()
