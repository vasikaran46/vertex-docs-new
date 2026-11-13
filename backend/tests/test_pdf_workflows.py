import io

from PIL import Image
from pypdf import PdfReader
import pymupdf
from reportlab.pdfgen import canvas as pdf_canvas

from tests.support import ApiTestCase


class PdfWorkflowTests(ApiTestCase):
    def multi_page_pdf(self):
        output = io.BytesIO()
        document = pdf_canvas.Canvas(output, pagesize=(200, 300))
        for label in ("FIRST PAGE", "SECOND PAGE", "THIRD PAGE"):
            document.drawString(20, 250, label)
            document.showPage()
        document.save()
        return output.getvalue()

    def page_text(self, content):
        reader = PdfReader(io.BytesIO(content))
        return [page.extract_text() or "" for page in reader.pages]

    def image_bytes(self, color):
        output = io.BytesIO()
        Image.new("RGB", (80, 100), color).save(output, format="PNG")
        return output.getvalue()

    def test_pdf_information_text_merge_split_rotate_and_page_selection(self):
        _, token = self.create_account()
        auth = {"Authorization": f"Bearer {token}"}
        source = self.multi_page_pdf()
        source_file = ("source.pdf", source, "application/pdf")

        info = self.client.post("/api/pdf/info", headers=auth, files={"file": source_file})
        self.assertEqual(info.status_code, 200, info.text)
        self.assertEqual(info.json()["pages"], 3)

        extracted = self.client.post("/api/pdf/text", headers=auth, files={"file": source_file})
        self.assertEqual(extracted.status_code, 200, extracted.text)
        self.assertIn("SECOND PAGE", extracted.json()["text"])

        merged = self.client.post(
            "/api/pdf/merge",
            headers=auth,
            files=[
                ("files", ("first.pdf", source, "application/pdf")),
                ("files", ("second.pdf", source, "application/pdf")),
            ],
        )
        self.assertEqual(merged.status_code, 200, merged.text)
        merged_pages = self.page_text(merged.content)
        self.assertEqual(len(merged_pages), 6)
        self.assertIn("THIRD PAGE", merged_pages[-1])

        split = self.client.post(
            "/api/pdf/split",
            headers=auth,
            data={"pages": "1,3"},
            files={"file": source_file},
        )
        self.assertEqual(split.status_code, 200, split.text)
        split_pages = self.page_text(split.content)
        self.assertEqual(len(split_pages), 2)
        self.assertIn("FIRST PAGE", split_pages[0])
        self.assertIn("THIRD PAGE", split_pages[1])

        removed = self.client.post(
            "/api/pdf/remove-pages",
            headers=auth,
            data={"pages": "1,3"},
            files={"file": source_file},
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        removed_pages = self.page_text(removed.content)
        self.assertEqual(len(removed_pages), 1)
        self.assertIn("SECOND PAGE", removed_pages[0])

        extracted_pages = self.client.post(
            "/api/pdf/extract-pages",
            headers=auth,
            data={"pages": "2"},
            files={"file": source_file},
        )
        self.assertEqual(extracted_pages.status_code, 200, extracted_pages.text)
        selected_pages = self.page_text(extracted_pages.content)
        self.assertEqual(len(selected_pages), 1)
        self.assertIn("SECOND PAGE", selected_pages[0])

        rotated = self.client.post(
            "/api/pdf/rotate",
            headers=auth,
            data={"degrees": "90"},
            files={"file": source_file},
        )
        self.assertEqual(rotated.status_code, 200, rotated.text)
        self.assertEqual(PdfReader(io.BytesIO(rotated.content)).pages[0].get("/Rotate"), 90)

    def test_pdf_password_protection_and_unlock_workflow(self):
        _, token = self.create_account()
        auth = {"Authorization": f"Bearer {token}"}
        source = self.multi_page_pdf()
        protected = self.client.post(
            "/api/pdf/protect",
            headers=auth,
            data={"password": "VertexTestPass"},
            files={"file": ("source.pdf", source, "application/pdf")},
        )
        self.assertEqual(protected.status_code, 200, protected.text)
        protected_reader = PdfReader(io.BytesIO(protected.content))
        self.assertTrue(protected_reader.is_encrypted)
        self.assertTrue(protected_reader.decrypt("VertexTestPass"))

        incorrect_password = self.client.post(
            "/api/pdf/unlock",
            headers=auth,
            data={"password": "incorrect"},
            files={"file": ("protected.pdf", protected.content, "application/pdf")},
        )
        self.assertEqual(incorrect_password.status_code, 400)
        self.assertIn("Incorrect PDF password", incorrect_password.json()["detail"])

        unlocked = self.client.post(
            "/api/pdf/unlock",
            headers=auth,
            data={"password": "VertexTestPass"},
            files={"file": ("protected.pdf", protected.content, "application/pdf")},
        )
        self.assertEqual(unlocked.status_code, 200, unlocked.text)
        unlocked_reader = PdfReader(io.BytesIO(unlocked.content))
        self.assertFalse(unlocked_reader.is_encrypted)
        self.assertEqual(len(unlocked_reader.pages), 3)
        self.assertIn("SECOND PAGE", unlocked_reader.pages[1].extract_text())

    def test_pdf_operations_reject_invalid_page_parameters(self):
        _, token = self.create_account()
        source = self.multi_page_pdf()
        rotated = self.client.post(
            "/api/pdf/rotate",
            headers={"Authorization": f"Bearer {token}"},
            data={"degrees": "45"},
            files={"file": ("source.pdf", source, "application/pdf")},
        )
        self.assertEqual(rotated.status_code, 400)

        empty_result = self.client.post(
            "/api/pdf/remove-pages",
            headers={"Authorization": f"Bearer {token}"},
            data={"pages": "1,2,3"},
            files={"file": ("source.pdf", source, "application/pdf")},
        )
        self.assertEqual(empty_result.status_code, 400)

        invalid_organization = self.client.post(
            "/api/pdf/organize",
            headers={"Authorization": f"Bearer {token}"},
            data={"page_order": "1,1"},
            files={"file": ("source.pdf", self.multi_page_pdf(), "application/pdf")},
        )
        self.assertEqual(invalid_organization.status_code, 400)

    def test_organize_pdf_reorders_rotates_and_removes_pages(self):
        _, token = self.create_account()
        response = self.client.post(
            "/api/pdf/organize",
            headers={"Authorization": f"Bearer {token}"},
            data={"page_order": "3,1", "rotations": "3:90"},
            files={"file": ("source.pdf", self.multi_page_pdf(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = PdfReader(io.BytesIO(response.content))
        self.assertEqual(len(result.pages), 2)
        self.assertIn("THIRD PAGE", result.pages[0].extract_text())
        self.assertIn("FIRST PAGE", result.pages[1].extract_text())
        self.assertEqual(result.pages[0].get("/Rotate"), 90)

    def test_scan_to_pdf_combines_ordered_images_and_applies_rotation(self):
        _, token = self.create_account()
        response = self.client.post(
            "/api/pdf/scan",
            headers={"Authorization": f"Bearer {token}"},
            data={"rotations": "90,0"},
            files=[
                ("files", ("first.png", self.image_bytes("red"), "image/png")),
                ("files", ("second.png", self.image_bytes("blue"), "image/png")),
            ],
        )
        self.assertEqual(response.status_code, 200, response.text)
        document = pymupdf.open(stream=response.content, filetype="pdf")
        self.assertEqual(document.page_count, 2)
        self.assertEqual(document[0].rotation, 90)
        for page, expected in ((document[0], "red"), (document[1], "blue")):
            pixmap = page.get_pixmap()
            offset = ((pixmap.height // 2) * pixmap.width + pixmap.width // 2) * pixmap.n
            red, green, blue = pixmap.samples[offset:offset + 3]
            self.assertGreater(red if expected == "red" else blue, 200)
            self.assertLess(blue if expected == "red" else red, 50)

    def test_scan_to_pdf_rejects_invalid_images_and_rotation_values(self):
        _, token = self.create_account()
        auth = {"Authorization": f"Bearer {token}"}
        invalid_image = self.client.post(
            "/api/pdf/scan",
            headers=auth,
            data={"rotations": "0"},
            files={"files": ("invalid.png", b"not an image", "image/png")},
        )
        self.assertEqual(invalid_image.status_code, 400)

        invalid_rotation = self.client.post(
            "/api/pdf/scan",
            headers=auth,
            data={"rotations": "45"},
            files={"files": ("page.png", self.image_bytes("white"), "image/png")},
        )
        self.assertEqual(invalid_rotation.status_code, 400)
