import io
import json
import zipfile

from PIL import Image
from pypdf import PdfReader
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject, TextStringObject
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas

from tests.support import ApiTestCase


class PdfToolTests(ApiTestCase):
    def make_pdf(self, labels):
        output = io.BytesIO()
        document = pdf_canvas.Canvas(output, pagesize=(200, 300))
        for label in labels:
            document.drawString(20, 250, label)
            document.showPage()
        document.save()
        return output.getvalue()

    def make_bookmarked_pdf(self):
        output = io.BytesIO()
        document = pdf_canvas.Canvas(output, pagesize=(200, 300))
        for index, label in enumerate(("FIRST", "SECOND", "THIRD")):
            document.drawString(20, 250, label)
            key = f"page-{index + 1}"
            document.bookmarkPage(key)
            document.addOutlineEntry(label, key, level=0)
            document.showPage()
        document.save()
        return output.getvalue()

    def make_form_pdf(self):
        output = io.BytesIO()
        document = pdf_canvas.Canvas(output, pagesize=(200, 300))
        document.acroForm.textfield(name="FullName", x=20, y=250, width=120, height=20)
        document.showPage()
        document.save()
        return output.getvalue()

    def make_image_pdf(self):
        image = io.BytesIO()
        Image.new("RGB", (40, 40), "green").save(image, format="PNG")
        output = io.BytesIO()
        document = pdf_canvas.Canvas(output, pagesize=(200, 300))
        image.seek(0)
        document.drawImage(ImageReader(image), 20, 200, width=40, height=40)
        document.save()
        return output.getvalue()

    def call_tool(self, token, tool, source, options=None, extra_files=None):
        files = [("file", ("source.pdf", source, "application/pdf"))]
        for index, content in enumerate(extra_files or []):
            files.append(("files", (f"extra-{index + 1}.pdf", content, "application/pdf")))
        return self.client.post(
            f"/api/pdf/tools/{tool}",
            headers={"Authorization": f"Bearer {token}"},
            data={"options": json.dumps(options or {})},
            files=files,
        )

    def test_page_numbering_watermark_crop_and_rename(self):
        _, token = self.create_account()
        source = self.make_pdf(["FIRST", "SECOND"])

        numbered = self.call_tool(token, "add-page-numbers", source, {"start": 7})
        self.assertEqual(numbered.status_code, 200, numbered.text)
        numbered_reader = PdfReader(io.BytesIO(numbered.content))
        self.assertIn("7", numbered_reader.pages[0].extract_text())
        self.assertIn("8", numbered_reader.pages[1].extract_text())

        watermarked = self.call_tool(token, "add-watermark", source, {"text": "DRAFT"})
        self.assertEqual(watermarked.status_code, 200, watermarked.text)
        self.assertIn("DRAFT", PdfReader(io.BytesIO(watermarked.content)).pages[0].extract_text())

        cropped = self.call_tool(token, "crop-pdf", source, {"margins": {"left": 10, "right": 10, "top": 0, "bottom": 0}})
        self.assertEqual(cropped.status_code, 200, cropped.text)
        source_width = float(PdfReader(io.BytesIO(source)).pages[0].cropbox.width)
        cropped_width = float(PdfReader(io.BytesIO(cropped.content)).pages[0].cropbox.width)
        self.assertAlmostEqual(cropped_width, source_width * 0.8, places=1)

        renamed = self.call_tool(token, "rename-pdf", source, {"filename": "renamed report"})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertIn('filename="renamed-report.pdf"', renamed.headers["content-disposition"])

    def test_alternate_split_and_compare_pdf(self):
        _, token = self.create_account()
        first = self.make_pdf(["A-1", "A-2"])
        second = self.make_pdf(["B-1", "B-2"])

        alternated = self.call_tool(token, "alternate-and-mix-pdf", first, extra_files=[second])
        self.assertEqual(alternated.status_code, 200, alternated.text)
        pages = [page.extract_text() for page in PdfReader(io.BytesIO(alternated.content)).pages]
        self.assertIn("A-1", pages[0])
        self.assertIn("B-1", pages[1])
        self.assertIn("A-2", pages[2])
        self.assertIn("B-2", pages[3])

        split = self.call_tool(token, "split-by-half", first)
        self.assertEqual(split.status_code, 200, split.text)
        with zipfile.ZipFile(io.BytesIO(split.content)) as archive:
            self.assertEqual(len(archive.namelist()), 2)
            self.assertEqual(len(PdfReader(io.BytesIO(archive.read("part-01.pdf"))).pages), 1)

        comparison = self.call_tool(token, "compare-pdf", first, extra_files=[second])
        self.assertEqual(comparison.status_code, 200, comparison.text)
        self.assertEqual(comparison.json()["changed_pages"], 2)
        self.assertFalse(comparison.json()["identical"])

    def test_bookmarks_metadata_signature_and_flatten(self):
        _, token = self.create_account()
        source = self.make_pdf(["FIRST", "SECOND"])

        bookmarked = self.call_tool(token, "create-bookmarks", source, {"bookmarks": "Start:1\nEnd:2"})
        self.assertEqual(bookmarked.status_code, 200, bookmarked.text)
        self.assertEqual(len(PdfReader(io.BytesIO(bookmarked.content)).outline), 2)

        metadata = self.call_tool(token, "edit-metadata", source, {"metadata": {"title": "Project Report", "author": "Alex"}})
        self.assertEqual(metadata.status_code, 200, metadata.text)
        self.assertEqual(PdfReader(io.BytesIO(metadata.content)).metadata.title, "Project Report")

        signed = self.call_tool(token, "sign-pdf", source, {"signature": "Alex Example"})
        self.assertEqual(signed.status_code, 200, signed.text)
        self.assertIn("Alex Example", PdfReader(io.BytesIO(signed.content)).pages[0].extract_text())

        flattened = self.call_tool(token, "flatten-pdf", source, {"dpi": 72})
        self.assertEqual(flattened.status_code, 200, flattened.text)
        flattened_reader = PdfReader(io.BytesIO(flattened.content))
        self.assertEqual(len(flattened_reader.pages), 2)
        self.assertFalse(flattened_reader.pages[0].extract_text())

    def test_pdf_tools_reject_invalid_options_and_unknown_fields(self):
        _, token = self.create_account()
        source = self.make_pdf(["FIRST"])

        invalid_crop = self.call_tool(token, "crop-pdf", source, {"margins": {"left": 90, "right": 10}})
        self.assertEqual(invalid_crop.status_code, 400)

        invalid_bookmark = self.call_tool(token, "create-bookmarks", source, {"bookmarks": "Bad page:3"})
        self.assertEqual(invalid_bookmark.status_code, 400)

        invalid_form = self.call_tool(token, "pdf-forms", source, {"values": {"No such field": "value"}})
        self.assertEqual(invalid_form.status_code, 400)

    def test_fill_form_fields_and_split_by_bookmark_text_and_size(self):
        _, token = self.create_account()
        form_pdf = self.make_form_pdf()
        fields = self.call_tool(token, "pdf-forms", form_pdf)
        self.assertEqual(fields.status_code, 200, fields.text)
        self.assertIn("FullName", fields.json()["fields"])
        filled = self.call_tool(token, "pdf-forms", form_pdf, {"values": {"FullName": "Alex Smith"}})
        self.assertEqual(filled.status_code, 200, filled.text)
        self.assertEqual(PdfReader(io.BytesIO(filled.content)).get_fields()["FullName"].get("/V"), "Alex Smith")

        source = self.make_bookmarked_pdf()
        by_bookmark = self.call_tool(token, "split-by-bookmarks", source)
        self.assertEqual(by_bookmark.status_code, 200, by_bookmark.text)
        with zipfile.ZipFile(io.BytesIO(by_bookmark.content)) as archive:
            self.assertEqual(len(archive.namelist()), 3)

        by_text = self.call_tool(token, "split-by-text", source, {"text": "SECOND"})
        self.assertEqual(by_text.status_code, 200, by_text.text)
        with zipfile.ZipFile(io.BytesIO(by_text.content)) as archive:
            self.assertEqual(len(archive.namelist()), 2)

        by_size = self.call_tool(token, "split-by-size", source, {"max_size_bytes": 100000})
        self.assertEqual(by_size.status_code, 200, by_size.text)
        with zipfile.ZipFile(io.BytesIO(by_size.content)) as archive:
            self.assertGreaterEqual(len(archive.namelist()), 1)

    def test_n_up_resize_flip_grayscale_and_repair(self):
        _, token = self.create_account()
        source = self.make_pdf(["FIRST", "SECOND"])

        n_up = self.call_tool(token, "n-up-pdf", source, {"pages_per_sheet": 2})
        self.assertEqual(n_up.status_code, 200, n_up.text)
        self.assertEqual(len(PdfReader(io.BytesIO(n_up.content)).pages), 1)

        resized = self.call_tool(token, "resize-pdf", source, {"paper": "Letter"})
        self.assertEqual(resized.status_code, 200, resized.text)
        self.assertAlmostEqual(float(PdfReader(io.BytesIO(resized.content)).pages[0].mediabox.width), 612, places=0)

        flipped = self.call_tool(token, "flip-pdf", source, {"direction": "horizontal"})
        self.assertEqual(flipped.status_code, 200, flipped.text)
        self.assertIn("FIRST", PdfReader(io.BytesIO(flipped.content)).pages[0].extract_text())

        grayscale = self.call_tool(token, "grayscale-pdf", source, {"dpi": 72})
        self.assertEqual(grayscale.status_code, 200, grayscale.text)
        self.assertEqual(len(PdfReader(io.BytesIO(grayscale.content)).pages), 2)

        repaired = self.call_tool(token, "repair-pdf", source)
        self.assertEqual(repaired.status_code, 200, repaired.text)
        self.assertEqual(len(PdfReader(io.BytesIO(repaired.content)).pages), 2)

    def test_extract_images_header_footer_bates_and_remove_annotations(self):
        _, token = self.create_account()
        source = self.make_image_pdf()

        images = self.call_tool(token, "extract-images", source)
        self.assertEqual(images.status_code, 200, images.text)
        with zipfile.ZipFile(io.BytesIO(images.content)) as archive:
            self.assertEqual(len(archive.namelist()), 1)

        marked = self.call_tool(token, "header-and-footer", source, {"header": "Header", "footer": "Footer"})
        self.assertEqual(marked.status_code, 200, marked.text)
        text = PdfReader(io.BytesIO(marked.content)).pages[0].extract_text()
        self.assertIn("Header", text)
        self.assertIn("Footer", text)

        bates = self.call_tool(token, "bates-numbering", source, {"prefix": "CASE-", "start": 10, "digits": 4})
        self.assertEqual(bates.status_code, 200, bates.text)
        self.assertIn("CASE-0010", PdfReader(io.BytesIO(bates.content)).pages[0].extract_text())

        writer = PdfWriter(clone_from=io.BytesIO(source))
        annotation = DictionaryObject()
        annotation.update({
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Text"),
            NameObject("/Rect"): ArrayObject([FloatObject(10), FloatObject(10), FloatObject(30), FloatObject(30)]),
            NameObject("/Contents"): TextStringObject("review"),
            NameObject("/F"): NumberObject(4),
        })
        writer.add_annotation(page_number=0, annotation=annotation)
        annotated = io.BytesIO()
        writer.write(annotated)
        removed = self.call_tool(token, "remove-annotations", annotated.getvalue())
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertNotIn("/Annots", PdfReader(io.BytesIO(removed.content)).pages[0])

        deskewed = self.call_tool(token, "deskew-pdf", source, {"dpi": 72})
        self.assertEqual(deskewed.status_code, 200, deskewed.text)
        self.assertEqual(len(PdfReader(io.BytesIO(deskewed.content)).pages), 1)
