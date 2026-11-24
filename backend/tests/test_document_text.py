import io
import os
import unittest
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document as WordDocument
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches

from app.extractive_summary import split_sentences, summarize
from app.ocr import available_languages, tesseract_executable
from tests.support import ApiTestCase


def docx_bytes(text: str) -> bytes:
    document = WordDocument()
    document.add_paragraph(text)
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Owner"
    table.rows[0].cells[1].text = "Vertex"
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def xlsx_bytes() -> bytes:
    workbook = Workbook()
    workbook.active.append(["Name", "Value"])
    workbook.active.append(["Vertex", 42])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def pptx_bytes(text: str) -> bytes:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2)).text = text
    output = io.BytesIO()
    presentation.save(output)
    return output.getvalue()


def epub_bytes(text: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>',
        )
        archive.writestr(
            "OEBPS/book.opf",
            '<package><manifest><item id="chapter" href="chapter.xhtml"/></manifest>'
            '<spine><itemref idref="chapter"/></spine></package>',
        )
        archive.writestr("OEBPS/chapter.xhtml", f"<html><body><p>{text}</p></body></html>")
    return output.getvalue()


def zip_bytes(text: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("notes.txt", text)
    return output.getvalue()


def text_image_bytes(text: str = "VERTEX OCR TEST") -> bytes:
    image = Image.new("RGB", (900, 260), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"
    try:
        font = ImageFont.truetype(str(font_path), 72) if font_path.is_file() else None
    except OSError:
        font = None
    if font is None:
        font = ImageFont.load_default()
    draw.text((30, 70), text, fill="black", font=font)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class ExtractiveSummaryTests(unittest.TestCase):
    def test_split_sentences_handles_tamil_hindi_and_english_punctuation(self):
        tamil = "முதல் வாக்கியம். இரண்டாம் வாக்கியம்! மூன்றாம் வாக்கியம்?"
        hindi = "पहला वाक्य। दूसरा वाक्य! तीसरा वाक्य?"
        english = "First sentence. Second sentence! Third sentence?"
        self.assertEqual(len(split_sentences(tamil)), 3)
        self.assertEqual(len(split_sentences(hindi)), 3)
        self.assertEqual(len(split_sentences(english)), 3)

    def test_summary_keeps_original_sentences_in_order(self):
        sentences = [
            "The project launched on Monday with a budget of 5000 dollars.",
            "The team measured customer feedback every week.",
            "Revenue grew by twelve percent in the first quarter.",
            "The support desk answered more than 400 tickets.",
            "A second office opened in the north of the city.",
            "The final report is due on Friday.",
        ]
        text = " ".join(sentences)
        summary = summarize(text, max_chars=140)
        self.assertTrue(summary.strip())
        self.assertLess(len(summary), len(text))
        for sentence in sentences:
            if sentence in summary:
                self.assertIn(sentence, text)
        selected = [sentence for sentence in sentences if sentence in summary]
        positions = [text.index(sentence) for sentence in selected]
        self.assertEqual(positions, sorted(positions))

    def test_summary_of_a_very_short_document_is_the_document(self):
        text = "Only one short sentence."
        self.assertEqual(summarize(text), text)


class DocumentTextExtractionTests(ApiTestCase):
    def extract(self, filename: str, content: bytes) -> dict:
        _, token = self.create_account()
        response = self.client.post(
            "/api/ai/chat/attachment-text",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, content, "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_office_html_epub_and_zip_documents_are_readable(self):
        cases = [
            ("notes.docx", docx_bytes("The launch date is Friday."), ["launch date", "Owner", "Vertex"]),
            ("sheet.xlsx", xlsx_bytes(), ["Vertex", "42"]),
            ("slides.pptx", pptx_bytes("Quarterly review on Monday"), ["Quarterly review"]),
            ("page.html", b"<html><body><h1>HTML heading</h1><p>Body text</p></body></html>", ["HTML heading", "Body text"]),
            ("book.epub", epub_bytes("EPUB chapter text"), ["EPUB chapter text"]),
            ("bundle.zip", zip_bytes("ZIP member text"), ["ZIP member text"]),
        ]
        for filename, content, expected in cases:
            with self.subTest(filename=filename):
                text = self.extract(filename, content)["text"]
                for value in expected:
                    self.assertIn(value, text)

    @unittest.skipUnless(
        tesseract_executable() and "eng" in available_languages(),
        "Tesseract with English data is not installed",
    )
    def test_images_and_scanned_pdfs_are_read_with_ocr(self):
        image = text_image_bytes()
        image_text = self.extract("scan.png", image)["text"].upper()
        self.assertIn("VERTEX", image_text)
        self.assertIn("OCR", image_text)

        pdf_buffer = io.BytesIO()
        Image.open(io.BytesIO(image)).convert("RGB").save(pdf_buffer, format="PDF")
        pdf_text = self.extract("scan.pdf", pdf_buffer.getvalue())["text"].upper()
        self.assertIn("VERTEX", pdf_text)


class ChatAttachmentOcrTests(ApiTestCase):
    @unittest.skipUnless(
        tesseract_executable() and "eng" in available_languages(),
        "Tesseract with English data is not installed",
    )
    def test_chat_attachments_use_ocr_for_images_and_scanned_pdfs(self):
        _, token = self.create_account()
        headers = {"Authorization": f"Bearer {token}"}
        image = text_image_bytes()

        response = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("scan.png", image, "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        record = response.json()
        self.assertTrue(record["is_image"])
        self.assertGreater(record["char_count"], 0)
        self.assertIn("VERTEX", record["text_preview"].upper())

        pdf_buffer = io.BytesIO()
        Image.open(io.BytesIO(image)).convert("RGB").save(pdf_buffer, format="PDF")
        response = self.client.post(
            "/api/ai/chat/attachments",
            headers=headers,
            files={"file": ("scan.pdf", pdf_buffer.getvalue(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        record = response.json()
        self.assertTrue(record["is_scanned"])
        self.assertIn("VERTEX", record["text_preview"].upper())
