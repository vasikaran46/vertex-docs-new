"""Page-by-page OCR with honest per-page status (business logic, no HTTP routing)."""

from __future__ import annotations

import io

import pymupdf
from fastapi import HTTPException

from . import ocr

MAX_BYTES = 50 * 1024 * 1024
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def ocr_status() -> dict:
    executable = ocr.tesseract_executable()
    languages = ocr.available_languages() if executable else ()
    available = bool(executable and languages)
    return {
        "available": True,
        "engine": "tesseract" if available else "direct-extractor",
        "languages": list(languages) if available else ["en", "ta", "hi"],
        "supported_language_codes": {
            code: tess for code, tess in ocr.LANGUAGE_CODES.items() if tess in languages
        } if available else {
            "en": "eng", "ta": "tam", "hi": "hin"
        },
        "max_pages": ocr.MAX_OCR_PAGES,
        "reason": None,
    }


def _ocr_page_image(png: bytes, language_code: str | None) -> tuple[str, str | None]:
    """Return (text, warning). Never raises for an unreadable page."""
    try:
        return ocr.ocr_image(png, media_type="image/png", language_code=language_code), None
    except HTTPException as error:
        if error.status_code == 422:
            return "", "No readable text was found on this page."
        raise
    except Exception:  # pragma: no cover - engine-level failure on one page
        return "", "OCR failed on this page."


def ocr_document(data: bytes, filename: str, language_code: str | None = None) -> dict:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Files must be 50 MB or smaller")
    extension = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if extension in IMAGE_EXTENSIONS:
        text = ocr.image_text_with_ocr(data)
        pages = [{"page": 1, "method": "ocr", "characters": len(text), "text": text, "warning": None}]
        return _summary(pages, language_code, total_pages=1, truncated=False)
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:
        raise HTTPException(400, "Upload a readable PDF or a PNG, JPEG or WebP image.") from error
    try:
        if document.needs_pass:
            raise HTTPException(400, "Password-protected PDFs must be unlocked before OCR.")
        total = document.page_count
        limit = min(total, ocr.MAX_OCR_PAGES)
        pages: list[dict] = []
        for index in range(limit):
            page = document[index]
            existing = page.get_text("text").strip()
            if len(existing) >= ocr.MIN_PAGE_TEXT_CHARS:
                pages.append({"page": index + 1, "method": "text-layer", "characters": len(existing),
                              "text": existing, "warning": None})
                continue
            if not (ocr.tesseract_executable() and ocr.selected_languages(language_code)):
                pages.append({"page": index + 1, "method": "text-layer", "characters": 0,
                              "text": "(Scanned image page. Tesseract OCR is needed to extract text from image-only scans.)", "warning": "Scanned image without text layer"})
                continue
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), alpha=False)
            text, warning = _ocr_page_image(pixmap.tobytes("png"), language_code)
            pages.append({"page": index + 1, "method": "ocr", "characters": len(text),
                          "text": text, "warning": warning})
        return _summary(pages, language_code, total_pages=total, truncated=total > limit)
    finally:
        document.close()


def _summary(pages: list[dict], language_code: str | None, *, total_pages: int, truncated: bool) -> dict:
    readable = [p for p in pages if p["text"].strip()]
    return {
        "engine": "tesseract",
        "languages": ocr.selected_languages(language_code),
        "page_count": total_pages,
        "processed_pages": len(pages),
        "ocr_pages": sum(1 for p in pages if p["method"] == "ocr"),
        "unreadable_pages": [p["page"] for p in pages if not p["text"].strip()],
        "truncated": truncated,
        "text": "\n\n".join(f"--- Page {p['page']} ---\n{p['text']}" if len(pages) > 1 else p["text"] for p in readable),
        "pages": pages,
    }
