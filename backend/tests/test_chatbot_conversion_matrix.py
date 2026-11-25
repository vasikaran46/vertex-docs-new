import io
import unittest
from pathlib import Path
from PIL import Image
from docx import Document as WordDocument
from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from pptx import Presentation as PowerPointPresentation
import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, SimpleDocTemplate
from reportlab.lib.styles import getSampleStyleSheet

from app.chatbot.convert import (
    CONVERTERS,
    get_conversion_options,
    run_chatbot_conversion,
    get_unique_filename,
    save_converted_document_for_user,
    is_libreoffice_available,
)
from app.chatbot.tools import (
    tool_convert_document,
    detect_fastpath_intent,
)
from app.chatbot.attachments import ingest_attachment
from app.chatbot.routes import attach_from_workspace_document, AttachFromDocumentIn
from app.storage_service import upload_document
from app.database import SessionLocal
from app.models import Document, User
from tests.support import ApiTestCase


def _make_docx(text: str = "Test Heading and Content", has_table: bool = True) -> bytes:
    doc = WordDocument()
    doc.add_heading("Heading 1 Title", level=1)
    doc.add_paragraph(text)
    doc.add_heading("Heading 2 Subtitle", level=2)
    doc.add_paragraph("Second paragraph with more information.")
    if has_table:
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "ColA"
        table.cell(0, 1).text = "ColB"
        table.cell(1, 0).text = "Val1"
        table.cell(1, 1).text = "Val2"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pdf(text: str = "Sample PDF Page Content") -> bytes:
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    pdf.build([Paragraph(text, styles["Normal"])])
    return buf.getvalue()


def _make_pptx(title: str = "Slide Title", body: str = "Slide bullet content") -> bytes:
    prs = PowerPointPresentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title
    slide.shapes.placeholders[1].text = body
    if slide.has_notes_slide:
        slide.notes_slide.notes_text_frame.text = "Author presentation note"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _make_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["Item", "Qty", "Price"])
    ws.append(["Widget", 10, 25.5])
    ws.append(["Gadget", 5, 12.0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_png() -> bytes:
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class ChatbotConversionMatrixTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.email, _ = self.create_account("MatrixTester")
        with SessionLocal() as db:
            self.user_id = db.query(User).filter_by(email=self.email).first().id

    # 1. DOCX inputs
    def test_docx_to_all_formats(self):
        docx_data = _make_docx("Testing Word document conversion matrix")

        # DOCX -> PDF
        res = run_chatbot_conversion(docx_data, "test.docx", "pdf")
        pdf_out, media, name = res
        self.assertEqual(media, "application/pdf")
        self.assertTrue(pdf_out.startswith(b"%PDF"))
        self.assertFalse(res.approximate)

        # DOCX -> TXT
        res = run_chatbot_conversion(docx_data, "test.docx", "txt")
        txt_out, media, name = res
        self.assertEqual(media, "text/plain; charset=utf-8")
        text_str = txt_out.decode("utf-8")
        self.assertIn("Heading 1 Title", text_str)
        self.assertIn("ColA", text_str)
        self.assertFalse(res.approximate)

        # DOCX -> PPTX
        res = run_chatbot_conversion(docx_data, "test.docx", "pptx")
        pptx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        self.assertTrue(res.approximate)
        prs = PowerPointPresentation(io.BytesIO(pptx_out))
        self.assertGreaterEqual(len(prs.slides), 2)

        # DOCX -> XLSX
        res = run_chatbot_conversion(docx_data, "test.docx", "xlsx")
        xlsx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(res.approximate)
        wb = load_workbook(io.BytesIO(xlsx_out))
        self.assertIn("Table 1", wb.sheetnames)

    # 2. PDF inputs
    def test_pdf_to_all_formats(self):
        pdf_data = _make_pdf("Testing PDF conversion matrix to multiple formats")

        # PDF -> DOCX
        res = run_chatbot_conversion(pdf_data, "test.pdf", "docx")
        docx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertFalse(res.approximate)
        doc = WordDocument(io.BytesIO(docx_out))
        self.assertTrue(len(doc.paragraphs) > 0)

        # PDF -> TXT
        res = run_chatbot_conversion(pdf_data, "test.pdf", "txt")
        txt_out, media, name = res
        self.assertEqual(media, "text/plain; charset=utf-8")
        self.assertFalse(res.approximate)
        self.assertIn("--- Page 1 ---", txt_out.decode("utf-8"))

        # PDF -> PPTX
        res = run_chatbot_conversion(pdf_data, "test.pdf", "pptx")
        pptx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        self.assertTrue(res.approximate)
        prs = PowerPointPresentation(io.BytesIO(pptx_out))
        self.assertGreaterEqual(len(prs.slides), 1)

        # PDF -> XLSX
        res = run_chatbot_conversion(pdf_data, "test.pdf", "xlsx")
        xlsx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(res.approximate)
        wb = load_workbook(io.BytesIO(xlsx_out))
        self.assertTrue(len(wb.sheetnames) > 0)

    # 3. TXT / MD inputs
    def test_txt_md_to_all_formats(self):
        txt_data = "Title Slide\nBullet line 1\nBullet line 2\n\nSecond Slide\nAnother bullet point\nTab1\tTab2".encode("utf-8")

        # TXT -> PDF
        res = run_chatbot_conversion(txt_data, "notes.txt", "pdf")
        pdf_out, media, name = res
        self.assertEqual(media, "application/pdf")
        self.assertTrue(pdf_out.startswith(b"%PDF"))
        self.assertFalse(res.approximate)

        # TXT -> DOCX
        res = run_chatbot_conversion(txt_data, "notes.txt", "docx")
        docx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        doc = WordDocument(io.BytesIO(docx_out))
        self.assertGreaterEqual(len(doc.paragraphs), 2)

        # TXT -> PPTX
        res = run_chatbot_conversion(txt_data, "notes.txt", "pptx")
        pptx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        self.assertTrue(res.approximate)
        prs = PowerPointPresentation(io.BytesIO(pptx_out))
        self.assertEqual(len(prs.slides), 2)

        # TXT -> XLSX
        res = run_chatbot_conversion(txt_data, "notes.txt", "xlsx")
        xlsx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(res.approximate)
        wb = load_workbook(io.BytesIO(xlsx_out))
        sheet = wb.active
        self.assertGreaterEqual(sheet.max_row, 3)

    # 4. PPTX inputs
    def test_pptx_to_formats(self):
        pptx_data = _make_pptx("Quarterly Strategy", "Achieve 200% growth")

        # PPTX -> TXT
        res = run_chatbot_conversion(pptx_data, "deck.pptx", "txt")
        txt_out, media, name = res
        self.assertEqual(media, "text/plain; charset=utf-8")
        text = txt_out.decode("utf-8")
        self.assertIn("Quarterly Strategy", text)
        self.assertIn("Achieve 200% growth", text)

        # PPTX -> DOCX
        res = run_chatbot_conversion(pptx_data, "deck.pptx", "docx")
        docx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        doc = WordDocument(io.BytesIO(docx_out))
        self.assertTrue(any("Quarterly Strategy" in p.text for p in doc.paragraphs))

        # PPTX -> PDF (engine check)
        if not is_libreoffice_available():
            with self.assertRaises(HTTPException) as cm:
                run_chatbot_conversion(pptx_data, "deck.pptx", "pdf")
            self.assertEqual(cm.exception.status_code, 503)
            self.assertEqual(cm.exception.detail.get("error_code"), "ENGINE_MISSING")

    # 5. XLSX inputs
    def test_xlsx_to_formats(self):
        xlsx_data = _make_xlsx()

        # XLSX -> TXT
        res = run_chatbot_conversion(xlsx_data, "data.xlsx", "txt")
        txt_out, media, name = res
        self.assertEqual(media, "text/plain; charset=utf-8")
        text = txt_out.decode("utf-8")
        self.assertIn("--- Sheet: Sales ---", text)
        self.assertIn("Widget", text)

        # XLSX -> DOCX
        res = run_chatbot_conversion(xlsx_data, "data.xlsx", "docx")
        docx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertTrue(res.approximate)
        doc = WordDocument(io.BytesIO(docx_out))
        self.assertTrue(len(doc.tables) > 0)

        # XLSX -> PDF (engine check)
        if not is_libreoffice_available():
            with self.assertRaises(HTTPException) as cm:
                run_chatbot_conversion(xlsx_data, "data.xlsx", "pdf")
            self.assertEqual(cm.exception.status_code, 503)
            self.assertEqual(cm.exception.detail.get("error_code"), "ENGINE_MISSING")

    # 6. Image inputs
    def test_image_to_formats(self):
        png_data = _make_png()

        # Image -> PDF
        res = run_chatbot_conversion(png_data, "photo.png", "pdf")
        pdf_out, media, name = res
        self.assertEqual(media, "application/pdf")
        self.assertTrue(pdf_out.startswith(b"%PDF"))

        # Image -> DOCX
        res = run_chatbot_conversion(png_data, "photo.png", "docx")
        docx_out, media, name = res
        self.assertEqual(media, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        doc = WordDocument(io.BytesIO(docx_out))
        self.assertTrue(len(doc.paragraphs) > 0)

    # 7. Options Endpoint logic
    def test_conversion_options(self):
        # Options for DOCX
        docx_opts = get_conversion_options("docx")
        formats = [o["format"] for o in docx_opts]
        self.assertIn("pdf", formats)
        self.assertIn("txt", formats)
        self.assertIn("pptx", formats)
        self.assertIn("xlsx", formats)
        self.assertNotIn("docx", formats)

        # Check approximate notes
        pptx_opt = next(o for o in docx_opts if o["format"] == "pptx")
        self.assertTrue(pptx_opt["approximate"])
        self.assertIn("approximate", pptx_opt["note"].lower())

        # Options for PPTX (when LibreOffice is not installed)
        pptx_opts = get_conversion_options("pptx")
        pdf_opt = next(o for o in pptx_opts if o["format"] == "pdf")
        if not is_libreoffice_available():
            self.assertFalse(pdf_opt["available"])
            self.assertIn("LibreOffice", pdf_opt["note"])

    # 8. Unique filename logic
    def test_unique_filename(self):
        with SessionLocal() as db:
            name1 = get_unique_filename(db, self.user_id, "report.pdf")
            self.assertEqual(name1, "report.pdf")

            # Save a document with that name
            import uuid
            doc1 = Document(
                owner_id=self.user_id,
                original_name="report.pdf",
                stored_name=f"{uuid.uuid4().hex}.pdf",
                content_type="application/pdf",
                size=100,
            )
            db.add(doc1)
            db.commit()

            name2 = get_unique_filename(db, self.user_id, "report.pdf")
            self.assertEqual(name2, "report (1).pdf")

    # 9. Tool execution and Fastpath intent detection
    def test_fastpath_intents(self):
        self.assertEqual(detect_fastpath_intent("convert this document to excel"), ("convert", "xlsx"))
        self.assertEqual(detect_fastpath_intent("convert to powerpoint"), ("convert", "pptx"))
        self.assertEqual(detect_fastpath_intent("make me a word version"), ("convert", "docx"))
        self.assertEqual(detect_fastpath_intent("save it as text"), ("convert", "txt"))
        self.assertEqual(detect_fastpath_intent("convert to pdf"), ("convert", "pdf"))

    # 10. End-to-end tool execution with attachment
    def test_tool_convert_document_docx_to_pptx_and_xlsx(self):
        docx_bytes = _make_docx("End to end chatbot test")
        att = ingest_attachment(
            "briefing.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            self.user_id,
        )

        with SessionLocal() as db:
            # DOCX -> PPTX
            res = tool_convert_document(att["id"], "pptx", self.user_id, db)
            self.assertEqual(res["status"], "success")
            self.assertTrue(res["approximate"])
            self.assertIn("briefing.pptx", res["filename"])
            self.assertEqual(res["artifact"]["type"], "download")
            self.assertIn("approximate", res["artifact"]["note"].lower())

            # DOCX -> XLSX
            res_x = tool_convert_document(att["id"], "xlsx", self.user_id, db)
            self.assertEqual(res_x["status"], "success")
            self.assertTrue(res_x["approximate"])
            self.assertIn("briefing.xlsx", res_x["filename"])

    # 11. Unicode handling: Tamil, Hindi, Japanese
    def test_unicode_text_handling(self):
        unicode_text = "English Text\nவணக்கம் (Tamil)\nनमस्ते (Hindi)\nこんにちは (Japanese)\n🚀 Emoji".encode("utf-8")
        # Should convert cleanly to docx, txt, pptx, xlsx without character encoding errors
        docx_out, _, _ = run_chatbot_conversion(unicode_text, "multi_lang.txt", "docx")
        self.assertGreater(len(docx_out), 0)

        txt_out, _, _ = run_chatbot_conversion(unicode_text, "multi_lang.txt", "txt")
        self.assertIn("வணக்கம்", txt_out.decode("utf-8"))

        pptx_out, _, _ = run_chatbot_conversion(unicode_text, "multi_lang.txt", "pptx")
        self.assertGreater(len(pptx_out), 0)

    # 12. PDF to Images (PNG ZIP)
    def test_pdf_to_images_conversion(self):
        pdf_data = _make_pdf("Page 1 Images Test")
        res = run_chatbot_conversion(pdf_data, "sample.pdf", "png")
        zip_bytes, media, filename = res
        self.assertEqual(media, "application/zip")
        self.assertTrue(filename.endswith(".zip"))

        import zipfile
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = zf.namelist()
        self.assertTrue(len(names) > 0)
        self.assertTrue(names[0].endswith(".png"))

    # 13. File validation: zero-bytes rejected
    def test_attachment_zero_bytes_rejected(self):
        with self.assertRaises(HTTPException) as cm:
            ingest_attachment("empty.txt", b"", "text/plain", self.user_id)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("0 bytes", cm.exception.detail)

    # 14. File validation: encrypted PDF rejected
    def test_attachment_encrypted_pdf_rejected(self):
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text((50, 50), "Secret")
        enc_bytes = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="1234", owner_pw="admin")

        with self.assertRaises(HTTPException) as cm:
            ingest_attachment("encrypted.pdf", enc_bytes, "application/pdf", self.user_id)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("password", cm.exception.detail.lower())

    # 15. Workspace document attachment
    def test_attach_from_workspace_document(self):
        import uuid
        stored_name = f"{uuid.uuid4().hex}.txt"
        upload_document(stored_name, b"Workspace doc content", "text/plain")

        with SessionLocal() as db:
            doc = Document(
                owner_id=self.user_id,
                original_name="workspace_notes.txt",
                stored_name=stored_name,
                content_type="text/plain",
                size=21,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            doc_id = doc.id

            user = db.query(User).filter_by(id=self.user_id).first()

            # Attach existing doc
            payload = AttachFromDocumentIn(document_id=doc_id)
            record = attach_from_workspace_document(payload, db=db, u=user)
            self.assertEqual(record["filename"], "workspace_notes.txt")
            self.assertEqual(record["extension"], ".txt")

            # Try to attach nonexistent document -> 404
            bad_payload = AttachFromDocumentIn(document_id=999999)
            with self.assertRaises(HTTPException) as cm:
                attach_from_workspace_document(bad_payload, db=db, u=user)
            self.assertEqual(cm.exception.status_code, 404)

            # Try to attach document belonging to another user -> 404
            other_user = User(
                email=f"other_{uuid.uuid4().hex[:6]}@example.com",
                password_hash="hash",
                name="Other User",
            )
            db.add(other_user)
            db.commit()
            db.refresh(other_user)

            with self.assertRaises(HTTPException) as cm:
                attach_from_workspace_document(payload, db=db, u=other_user)
            self.assertEqual(cm.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
