import io
from docx import Document as WordDocument
import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, SimpleDocTemplate
from reportlab.lib.styles import getSampleStyleSheet
from tests.support import ApiTestCase
from app.chatbot.convert import detect_conversion_intent
from app.chatbot.attachments import format_chat_prompt


def _create_sample_docx(text: str = "Straw Hat Pirates sailed towards the Grand Line.") -> bytes:
    doc = WordDocument()
    doc.add_heading("Chapter 1: The Voyage", level=1)
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _create_sample_pdf(text: str = "Monkey D. Luffy seeks the legendary treasure.") -> bytes:
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    pdf.build([Paragraph(text, styles["Normal"])])
    return buf.getvalue()


def _create_blank_scanned_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)  # Empty white page with no text
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class ChatbotFeatureTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        from app.chatbot.attachments import META_FILE
        if META_FILE.exists():
            try:
                META_FILE.unlink(missing_ok=True)
            except Exception:
                pass

    def test_attachment_upload_and_extraction_docx_txt_pdf(self):
        _, token = self.create_account("ChatUser")
        headers = {"Authorization": f"Bearer {token}"}

        # 1. DOCX attachment
        docx_bytes = _create_sample_docx("One Piece is the treasure left by Gol D. Roger.")
        resp_docx = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("onepiece.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        self.assertEqual(resp_docx.status_code, 200, resp_docx.text)
        docx_data = resp_docx.json()
        self.assertIn("One Piece is the treasure", docx_data["text_preview"])
        self.assertEqual(docx_data["extension"], ".docx")
        self.assertFalse(docx_data["is_scanned"])

        # 2. Plain TXT attachment
        txt_bytes = b"Luffy recruit Zoro as his first crewmate in Shells Town."
        resp_txt = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("notes.txt", txt_bytes, "text/plain")},
        )
        self.assertEqual(resp_txt.status_code, 200, resp_txt.text)
        txt_data = resp_txt.json()
        self.assertIn("Luffy recruit Zoro", txt_data["text_preview"])

        # 3. PDF attachment
        pdf_bytes = _create_sample_pdf("Nami navigates through dangerous ocean storms.")
        resp_pdf = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("story.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(resp_pdf.status_code, 200, resp_pdf.text)
        pdf_data = resp_pdf.json()
        self.assertIn("Nami navigates", pdf_data["text_preview"])
        self.assertFalse(pdf_data["is_scanned"])

    def test_scanned_pdf_returns_ocr_notice(self):
        _, token = self.create_account("ScanUser")
        headers = {"Authorization": f"Bearer {token}"}

        blank_pdf = _create_blank_scanned_pdf()
        resp = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("scanned.pdf", blank_pdf, "application/pdf")},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data["is_scanned"])
        self.assertIn("OCR not available", data["text_preview"])

    def test_unsupported_attachment_rejection(self):
        _, token = self.create_account("RejectUser")
        headers = {"Authorization": f"Bearer {token}"}

        resp = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("script.exe", b"binarycontent", "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 415, resp.text)

    def test_chatbot_conversion_docx_to_pdf_and_pdf_to_docx(self):
        _, token = self.create_account("ConvertUser")
        headers = {"Authorization": f"Bearer {token}"}

        # Upload DOCX
        docx_bytes = _create_sample_docx("Going Merry sails to the Grand Line.")
        upload_resp = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("story.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        self.assertEqual(upload_resp.status_code, 200)
        att_id = upload_resp.json()["id"]

        # Convert DOCX to PDF
        conv_resp = self.client.post(
            "/api/ai/chat/convert",
            headers=headers,
            data={"attachment_id": att_id, "target_format": "pdf"},
        )
        self.assertEqual(conv_resp.status_code, 200, conv_resp.text)
        card = conv_resp.json()["card"]
        self.assertTrue(card["filename"].endswith(".pdf"))
        self.assertGreater(card["size"], 500)
        self.assertIn("/api/documents/", card["download_url"])

        # Verify converted file can be downloaded
        dl_resp = self.client.get(card["download_url"], headers=headers)
        self.assertEqual(dl_resp.status_code, 200)
        self.assertEqual(dl_resp.headers["content-type"], "application/pdf")

    def test_owner_isolation_for_attachments_and_conversations(self):
        _, token_a = self.create_account("UserA")
        _, token_b = self.create_account("UserB")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User A creates attachment and conversation
        docx_bytes = _create_sample_docx("Private notes")
        upload_resp = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers_a,
            files={"file": ("private.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        att_id = upload_resp.json()["id"]

        conv_resp = self.client.post("/api/ai/conversations", headers=headers_a)
        conv_id = conv_resp.json()["id"]

        # User B should NOT be able to view attachment info or download it
        self.assertEqual(self.client.get(f"/api/ai/chat/attachments/{att_id}", headers=headers_b).status_code, 404)
        self.assertEqual(self.client.get(f"/api/ai/chat/attachments/{att_id}/file", headers=headers_b).status_code, 404)

        # User B cannot convert User A's attachment
        convert_b = self.client.post(
            "/api/ai/chat/convert",
            headers=headers_b,
            data={"attachment_id": att_id, "target_format": "pdf"},
        )
        self.assertEqual(convert_b.status_code, 404)

        # User B cannot view or rename User A's conversation
        self.assertEqual(self.client.get(f"/api/ai/conversations/{conv_id}", headers=headers_b).status_code, 404)
        rename_b = self.client.patch(
            f"/api/ai/conversations/{conv_id}",
            headers=headers_b,
            json={"title": "Hacked Title"},
        )
        self.assertEqual(rename_b.status_code, 404)

    def test_rename_and_get_conversation_with_attachments(self):
        _, token = self.create_account("RenameUser")
        headers = {"Authorization": f"Bearer {token}"}

        conv = self.client.post("/api/ai/conversations", headers=headers).json()
        conv_id = conv["id"]

        # Rename
        rename_resp = self.client.patch(
            f"/api/ai/conversations/{conv_id}",
            headers=headers,
            json={"title": "One Piece Analysis"},
        )
        self.assertEqual(rename_resp.status_code, 200)
        self.assertEqual(rename_resp.json()["title"], "One Piece Analysis")

        # Upload attachment linked to this conversation
        docx_bytes = _create_sample_docx("Straw Hat Adventure")
        self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("onepiece.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"conversation_id": str(conv_id)},
        )

        # Get conversation detail
        detail = self.client.get(f"/api/ai/conversations/{conv_id}", headers=headers).json()
        self.assertEqual(detail["title"], "One Piece Analysis")
        self.assertEqual(len(detail["attachments"]), 1)
        self.assertEqual(detail["attachments"][0]["filename"], "onepiece.docx")

    def test_detect_conversion_intent(self):
        self.assertEqual(detect_conversion_intent("Please convert this to pdf"), "pdf")
        self.assertEqual(detect_conversion_intent("convert this document to docx"), "docx")
        self.assertEqual(detect_conversion_intent("can you export to txt?"), "txt")
        self.assertIsNone(detect_conversion_intent("Summarize chapter 2 of this file"))

    def test_format_chat_prompt_includes_document_content(self):
        att_records = [{
            "filename": "onepiece_story.docx",
            "is_image": False,
            "extracted_text": "Luffy sets sail from Foosha Village to find the One Piece.",
        }]
        prompt, names = format_chat_prompt("Who is the main character?", att_records, "main character")
        self.assertIn("DOCUMENT CONTENT (onepiece_story.docx):", prompt)
        self.assertIn("Foosha Village", prompt)
        self.assertIn("USER QUESTION:\nWho is the main character?", prompt)
        self.assertIn("onepiece_story.docx", names)
