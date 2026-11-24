import io
import unittest

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from app import ocr
from app.ocr_service import ocr_status
from tests.support import ApiTestCase


def text_image(text: str) -> bytes:
    image = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
    draw.text((30, 60), text, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def scanned_pdf(*words: str) -> bytes:
    doc = pymupdf.open()
    for word in words:
        page = doc.new_page()
        page.insert_image(page.rect, stream=text_image(word))
    data = doc.tobytes()
    doc.close()
    return data


ENGINE = ocr_status()["available"] and "eng" in ocr.available_languages()


class OcrEndpointTests(ApiTestCase):
    def headers(self):
        _, token = self.create_account()
        return {"Authorization": f"Bearer {token}"}

    def test_status_reports_real_engine_state(self):
        r = self.client.get("/api/pdf/ocr/status", headers=self.headers())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("available", body)
        if not body["available"]:
            self.assertTrue(body["reason"])

    def test_requires_login_and_rejects_garbage(self):
        self.assertEqual(self.client.post("/api/pdf/ocr", files={"file": ("a.pdf", b"x", "application/pdf")}).status_code, 401)
        r = self.client.post("/api/pdf/ocr", headers=self.headers(), files={"file": ("a.pdf", b"not a pdf", "application/pdf")})
        self.assertEqual(r.status_code, 400)

    def test_text_layer_pdf_needs_no_ocr(self):
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "This page already has selectable text.")
        data = doc.tobytes()
        r = self.client.post("/api/pdf/ocr", headers=self.headers(), files={"file": ("t.pdf", data, "application/pdf")})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["ocr_pages"], 0)
        self.assertEqual(body["pages"][0]["method"], "text-layer")
        self.assertIn("selectable text", body["text"])

    @unittest.skipUnless(ENGINE, "Tesseract with English data is not installed")
    def test_scanned_multi_page_pdf_is_read_with_ocr(self):
        r = self.client.post("/api/pdf/ocr", headers=self.headers(), data={"language": "en"},
                             files={"file": ("scan.pdf", scanned_pdf("INVOICE", "RECEIPT"), "application/pdf")})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["page_count"], 2)
        self.assertEqual(body["ocr_pages"], 2)
        joined = body["text"].upper()
        self.assertIn("INVOICE", joined)
        self.assertIn("RECEIPT", joined)
        self.assertEqual(body["unreadable_pages"], [])

    @unittest.skipUnless(ENGINE, "Tesseract with English data is not installed")
    def test_image_upload_is_read_with_ocr(self):
        r = self.client.post("/api/pdf/ocr", headers=self.headers(), data={"language": "en"},
                             files={"file": ("scan.png", text_image("HELLO WORLD"), "image/png")})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("HELLO", r.json()["text"].upper())

    @unittest.skipUnless(ENGINE, "Tesseract with English data is not installed")
    def test_blank_scanned_page_is_reported_unreadable_not_faked(self):
        doc = pymupdf.open()
        page = doc.new_page()
        image = Image.new("RGB", (400, 400), "white")
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        page.insert_image(page.rect, stream=buffer.getvalue())
        data = doc.tobytes()
        r = self.client.post("/api/pdf/ocr", headers=self.headers(), data={"language": "en"},
                             files={"file": ("blank.pdf", data, "application/pdf")})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["unreadable_pages"], [1])
        self.assertTrue(body["pages"][0]["warning"])
        self.assertEqual(body["text"], "")


if __name__ == "__main__":
    unittest.main()
