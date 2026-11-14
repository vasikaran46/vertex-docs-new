import io
from docx import Document as WordDocument
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, SimpleDocTemplate
from reportlab.lib.styles import getSampleStyleSheet
from fastapi import HTTPException
from tests.support import ApiTestCase
from app.database import SessionLocal
from app.models import User
from app.chatbot.tools import (
    tool_convert_document,
    tool_read_document,
    tool_get_document_info,
    detect_fastpath_intent,
)
from app.chatbot.attachments import ingest_attachment


def _make_docx(text: str = "Straw Hat Pirates Adventure") -> bytes:
    doc = WordDocument()
    doc.add_heading("Chapter 1", level=1)
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pdf(text: str = "Grand Line navigation notes") -> bytes:
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    pdf.build([Paragraph(text, styles["Normal"])])
    return buf.getvalue()


def _get_user_id(email: str) -> int:
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=email).first()
        return user.id


class ChatbotToolsTests(ApiTestCase):
    def test_convert_document_docx_to_pdf_and_pdf_to_docx(self):
        email, _ = self.create_account("ToolUser")
        user_id = _get_user_id(email)
        docx_bytes = _make_docx("Luffy reaches Wano country.")
        att = ingest_attachment("wano.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", user_id)

        with SessionLocal() as db:
            # 1. DOCX -> PDF
            res = tool_convert_document(att["id"], "pdf", user_id, db)
            self.assertEqual(res["status"], "success")
            artifact = res["artifact"]
            self.assertTrue(artifact["filename"].endswith(".pdf"))
            self.assertEqual(artifact["type"], "download")
            self.assertGreater(artifact["size"], 500)

            # 2. PDF -> DOCX
            pdf_bytes = _make_pdf("Zoro trains his swordsmanship.")
            att_pdf = ingest_attachment("zoro.pdf", pdf_bytes, "application/pdf", user_id)
            res_docx = tool_convert_document(att_pdf["id"], "docx", user_id, db)
            self.assertEqual(res_docx["status"], "success")
            self.assertTrue(res_docx["artifact"]["filename"].endswith(".docx"))

            # 3. TXT -> PDF
            att_txt = ingest_attachment("crew.txt", b"Nami, Sanji, Chopper, Robin", "text/plain", user_id)
            res_txt = tool_convert_document(att_txt["id"], "pdf", user_id, db)
            self.assertEqual(res_txt["status"], "success")
            self.assertTrue(res_txt["artifact"]["filename"].endswith(".pdf"))

    def test_convert_permission_check_rejects_other_user(self):
        email_a, _ = self.create_account("OwnerUser")
        email_b, _ = self.create_account("AttackerUser")
        user_a_id = _get_user_id(email_a)
        user_b_id = _get_user_id(email_b)

        docx_bytes = _make_docx("Secret pirate treasure map.")
        att = ingest_attachment("secret.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", user_a_id)

        # User B cannot convert User A's attachment
        with SessionLocal() as db:
            with self.assertRaises(HTTPException) as ctx:
                tool_convert_document(att["id"], "pdf", user_b_id, db)
            self.assertEqual(ctx.exception.status_code, 404)

    def test_unsupported_conversion_returns_415(self):
        email, _ = self.create_account("UnsupportedUser")
        user_id = _get_user_id(email)
        docx_bytes = _make_docx("Some text")
        att = ingest_attachment("doc.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", user_id)

        with SessionLocal() as db:
            with self.assertRaises(HTTPException) as ctx:
                tool_convert_document(att["id"], "exe", user_id, db)
            self.assertEqual(ctx.exception.status_code, 415)
            self.assertIn("Coming soon", ctx.exception.detail)

    def test_detect_fastpath_intent(self):
        self.assertEqual(detect_fastpath_intent("convert to pdf"), ("convert", "pdf"))
        self.assertEqual(detect_fastpath_intent("please convert this document to docx"), ("convert", "docx"))
        self.assertEqual(detect_fastpath_intent("make this a pdf"), ("convert", "pdf"))
        self.assertEqual(detect_fastpath_intent("give me a txt"), ("convert", "txt"))
        self.assertEqual(detect_fastpath_intent("summarize this document"), ("summarize", "concise"))
        self.assertEqual(detect_fastpath_intent("key points"), ("key_points", None))
        self.assertIsNone(detect_fastpath_intent("Who is the captain of the ship?"))

    def test_read_document_and_info_tools(self):
        email, _ = self.create_account("InfoUser")
        user_id = _get_user_id(email)
        docx_bytes = _make_docx("Sanji cooks delicious feasts for the crew.")
        att = ingest_attachment("sanji.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", user_id)

        # Read document
        read_res = tool_read_document(att["id"], user_id)
        self.assertIn("Sanji cooks", read_res["content"])

        # Info tool
        info_res = tool_get_document_info(att["id"], user_id)
        self.assertEqual(info_res["filename"], "sanji.docx")
        self.assertGreater(info_res["word_count"], 3)

    def test_api_chat_convert_endpoint(self):
        _, token = self.create_account("EndpointUser")
        headers = {"Authorization": f"Bearer {token}"}

        docx_bytes = _make_docx("Test for direct convert endpoint.")
        upload_resp = self.client.post(
            "/api/chat/attachments",
            headers=headers,
            files={"file": ("test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        att_id = upload_resp.json()["id"]

        # Call direct /api/chat/convert
        resp = self.client.post(
            "/api/chat/convert",
            headers=headers,
            data={"attachment_id": att_id, "target_format": "pdf"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        art = resp.json()["artifact"]
        self.assertEqual(art["type"], "download")
        self.assertTrue(art["filename"].endswith(".pdf"))

    def test_api_chat_message_fastpath_conversion(self):
        _, token = self.create_account("FastpathUser")
        headers = {"Authorization": f"Bearer {token}"}

        docx_bytes = _make_docx("Thousand Sunny sails on.")
        upload_resp = self.client.post(
            "/api/chat/attachments",
            headers=headers,
            files={"file": ("sunny.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        att_id = upload_resp.json()["id"]

        # Send "convert to pdf" message to /api/chat/message (stream=False)
        msg_resp = self.client.post(
            "/api/chat/message",
            headers=headers,
            json={
                "text": "convert to pdf",
                "attachment_ids": [att_id],
                "stream": False,
            },
        )
        self.assertEqual(msg_resp.status_code, 200, msg_resp.text)
        data = msg_resp.json()
        self.assertEqual(len(data["artifacts"]), 1)
        self.assertTrue(data["artifacts"][0]["filename"].endswith(".pdf"))
        self.assertIn("converted", data["text"].lower())

    def test_conversion_output_is_outside_reload_watched_app_directory(self):
        from pathlib import Path
        from app.chatbot.convert import DOCUMENTS_STORE
        app_dir = Path(__file__).resolve().parents[1] / "app"
        # The storage directory must NOT be inside the reload-watched app folder
        self.assertFalse(
            DOCUMENTS_STORE.resolve().is_relative_to(app_dir.resolve()),
            f"DOCUMENTS_STORE ({DOCUMENTS_STORE}) must be outside app directory ({app_dir})"
        )
