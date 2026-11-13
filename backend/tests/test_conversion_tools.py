import io
import zipfile

from docx import Document as WordDocument
from openpyxl import Workbook, load_workbook
from PIL import Image
from pptx import Presentation
from pptx.util import Inches
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from app.conversion_service import _libreoffice_convert

from tests.support import ApiTestCase


class ConversionToolsTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        _, self.token = self.create_account()

    def convert(self, filename, content, output_format):
        return self.client.post(
            "/api/pdf/convert",
            headers={"Authorization": f"Bearer {self.token}"},
            data={"output_format": output_format},
            files={"file": (filename, content, "application/octet-stream")},
        )

    def word_bytes(self):
        document = WordDocument()
        document.add_paragraph("Vertex conversion sample")
        output = io.BytesIO()
        document.save(output)
        return output.getvalue()

    def text_pdf(self):
        output = io.BytesIO()
        document = pdf_canvas.Canvas(output, pagesize=A4)
        document.drawString(72, 760, "Vertex conversion sample")
        document.showPage()
        document.save()
        return output.getvalue()

    def spreadsheet_bytes(self):
        workbook = Workbook()
        workbook.active.append(["Name", "Value"])
        workbook.active.append(["Vertex", 42])
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()

    def presentation_bytes(self):
        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1)).text = "Vertex conversion sample"
        output = io.BytesIO()
        presentation.save(output)
        return output.getvalue()

    def test_word_pdf_and_pdf_export_formats(self):
        word = self.convert("sample.docx", self.word_bytes(), "pdf")
        self.assertEqual(word.status_code, 200, word.text)
        self.assertIn("Vertex conversion sample", PdfReader(io.BytesIO(word.content)).pages[0].extract_text())

        source_pdf = self.text_pdf()
        word_result = self.convert("sample.pdf", source_pdf, "docx")
        self.assertEqual(word_result.status_code, 200, word_result.text)
        converted_word = WordDocument(io.BytesIO(word_result.content))
        self.assertIn("Vertex conversion sample", "\n".join(item.text for item in converted_word.paragraphs))

        slides_result = self.convert("sample.pdf", source_pdf, "pptx")
        self.assertEqual(slides_result.status_code, 200, slides_result.text)
        self.assertEqual(len(Presentation(io.BytesIO(slides_result.content)).slides), 1)

        sheet_result = self.convert("sample.pdf", source_pdf, "xlsx")
        self.assertEqual(sheet_result.status_code, 200, sheet_result.text)
        workbook = load_workbook(io.BytesIO(sheet_result.content), read_only=True)
        values = [cell for row in workbook.active.iter_rows(values_only=True) for cell in row]
        self.assertIn("Vertex conversion sample", values)

        for output_format in ("jpg", "png"):
            images = self.convert("sample.pdf", source_pdf, output_format)
            self.assertEqual(images.status_code, 200, images.text)
            with zipfile.ZipFile(io.BytesIO(images.content)) as archive:
                self.assertEqual(archive.namelist(), [f"page-001.{output_format}"])
                with Image.open(io.BytesIO(archive.read(archive.namelist()[0]))) as image:
                    expected_image_format = "JPEG" if output_format == "jpg" else "PNG"
                    self.assertEqual(image.format, expected_image_format)

        markdown = self.convert("sample.pdf", source_pdf, "md")
        self.assertEqual(markdown.status_code, 200, markdown.text)
        self.assertIn("## Page 1", markdown.text)
        self.assertIn("Vertex conversion sample", markdown.text)

        pdfa = self.convert("sample.pdf", source_pdf, "pdfa")
        self.assertEqual(pdfa.status_code, 200, pdfa.text)
        converted_pdfa = PdfReader(io.BytesIO(pdfa.content))
        self.assertEqual(len(converted_pdfa.pages), 1)
        self.assertTrue(converted_pdfa.trailer["/Root"].get("/OutputIntents"))
        self.assertIsNotNone(converted_pdfa.trailer["/Root"].get("/Metadata"))

    def test_jpeg_and_webp_source_images_convert_to_pdf(self):
        image = Image.new("RGB", (80, 120), "#34734b")
        for extension, image_format in (("jpg", "JPEG"), ("jpeg", "JPEG"), ("webp", "WEBP")):
            with self.subTest(extension=extension):
                source = io.BytesIO()
                image.save(source, format=image_format)
                response = self.convert(f"sample.{extension}", source.getvalue(), "pdf")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers["content-type"], "application/pdf")
                self.assertEqual(len(PdfReader(io.BytesIO(response.content)).pages), 1)

    def test_spreadsheet_presentation_text_html_and_rtf_convert_to_pdf(self):
        cases = [
            ("sample.xlsx", self.spreadsheet_bytes(), "Vertex"),
            ("sample.pptx", self.presentation_bytes(), "Vertex conversion sample"),
            ("sample.html", b"<html><body><h1>Vertex HTML conversion</h1></body></html>", "Vertex HTML conversion"),
            ("sample.csv", b"Name,Value\nVertex,42\n", "Vertex"),
            ("sample.rtf", b"{\\rtf1\\ansi Vertex RTF conversion}", "Vertex RTF conversion"),
            ("sample.txt", b"Vertex plain text conversion", "Vertex plain text conversion"),
            ("sample.md", b"# Vertex Markdown conversion", "Vertex Markdown conversion"),
        ]
        for filename, content, expected_text in cases:
            with self.subTest(filename=filename):
                response = self.convert(filename, content, "pdf")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers["content-type"], "application/pdf")
                pages = PdfReader(io.BytesIO(response.content)).pages
                self.assertGreater(len(pages), 0)
                self.assertIn(expected_text, "\n".join(page.extract_text() or "" for page in pages))

    def test_legacy_and_open_document_office_formats_convert_to_readable_pdf(self):
        word = self.word_bytes()
        spreadsheet = self.spreadsheet_bytes()
        presentation = self.presentation_bytes()
        cases = [
            ("sample.doc", _libreoffice_convert(word, "docx", "doc", "doc")),
            ("sample.odt", _libreoffice_convert(word, "docx", "odt", "odt")),
            ("sample.xls", _libreoffice_convert(spreadsheet, "xlsx", "xls", "xls")),
            ("sample.ods", _libreoffice_convert(spreadsheet, "xlsx", "ods", "ods")),
            ("sample.ppt", _libreoffice_convert(presentation, "pptx", "ppt", "ppt")),
            ("sample.odp", _libreoffice_convert(presentation, "pptx", "odp", "odp")),
        ]
        for filename, content in cases:
            with self.subTest(filename=filename):
                response = self.convert(filename, content, "pdf")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers["content-type"], "application/pdf")
                pages = PdfReader(io.BytesIO(response.content)).pages
                self.assertGreater(len(pages), 0)
                text = "\n".join(page.extract_text() or "" for page in pages)
                expected = "Vertex" if filename.endswith(("doc", "odt", "ppt", "odp")) else "Name"
                self.assertIn(expected, text)

    def test_epub_zip_and_pages_previews_convert_to_pdf(self):
        epub = io.BytesIO()
        with zipfile.ZipFile(epub, "w") as archive:
            archive.writestr(
                "META-INF/container.xml",
                '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>',
            )
            archive.writestr(
                "OEBPS/book.opf",
                '<package><manifest><item id="chapter" href="chapter.xhtml"/></manifest>'
                '<spine><itemref idref="chapter"/></spine></package>',
            )
            archive.writestr(
                "OEBPS/chapter.xhtml",
                "<html><body><h1>EPUB chapter</h1><p>Converted content.</p></body></html>",
            )
        epub_result = self.convert("sample.epub", epub.getvalue(), "pdf")
        self.assertEqual(epub_result.status_code, 200, epub_result.text)
        self.assertIn("EPUB chapter", PdfReader(io.BytesIO(epub_result.content)).pages[0].extract_text())

        image_data = io.BytesIO()
        Image.new("RGB", (20, 20), "#34734b").save(image_data, format="PNG")
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w") as archive:
            archive.writestr("first.pdf", self.text_pdf())
            archive.writestr("second.png", image_data.getvalue())
        zip_result = self.convert("sample.zip", archive_data.getvalue(), "pdf")
        self.assertEqual(zip_result.status_code, 200, zip_result.text)
        self.assertEqual(len(PdfReader(io.BytesIO(zip_result.content)).pages), 2)

        pages_file = io.BytesIO()
        with zipfile.ZipFile(pages_file, "w") as archive:
            archive.writestr("QuickLook/Preview.pdf", self.text_pdf())
        pages_result = self.convert("sample.pages", pages_file.getvalue(), "pdf")
        self.assertEqual(pages_result.status_code, 200, pages_result.text)
        self.assertEqual(len(PdfReader(io.BytesIO(pages_result.content)).pages), 1)

    def test_unsupported_format_returns_a_clear_error(self):
        response = self.convert("sample.exe", b"not a document", "pdf")
        self.assertEqual(response.status_code, 415)
        self.assertIn("not supported", response.json()["detail"])
