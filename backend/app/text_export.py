"""Export plain text (translations, humanized text, OCR results) as real files."""

from __future__ import annotations

import io
import json
import re
from html import escape as html_escape
from pathlib import PurePath

from docx import Document as WordDocument
from fastapi import HTTPException
from pptx import Presentation
from pptx.util import Inches, Pt

from .conversion_service import _text_to_pdf

SUPPORTED_FORMATS = ("txt", "md", "html", "docx", "pdf", "rtf", "pptx", "json")
MAX_CHARS = 500_000
MEDIA_TYPES = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "rtf": "application/rtf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "json": "application/json",
}
_SAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_stem(title: str | None) -> str:
    stem = PurePath(title or "vertex-export").stem
    stem = _SAFE.sub("", stem).strip(" .-_") or "vertex-export"
    return stem[:80]


def _paragraphs(text: str) -> list[str]:
    return [block.strip("\n") for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]


def _rtf(text: str) -> bytes:
    out = []
    for char in text:
        code = ord(char)
        if char in "\\{}":
            out.append("\\" + char)
        elif char == "\n":
            out.append("\\par\n")
        elif code < 128:
            out.append(char)
        else:
            signed = code - 65536 if code > 32767 else code
            if code > 0xFFFF:
                high = 0xD800 + ((code - 0x10000) >> 10)
                low = 0xDC00 + ((code - 0x10000) & 0x3FF)
                out.append(f"\\u{high - 65536}?\\u{low - 65536}?")
            else:
                out.append(f"\\u{signed}?")
    return ("{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\f0\\fs24 " + "".join(out) + "}").encode("ascii")


def _docx(text: str, title: str) -> bytes:
    document = WordDocument()
    document.add_heading(title, level=1)
    for block in _paragraphs(text):
        paragraph = document.add_paragraph()
        for index, line in enumerate(block.split("\n")):
            if index:
                paragraph.add_run().add_break()
            paragraph.add_run(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pptx(text: str, title: str) -> bytes:
    presentation = Presentation()
    blocks = _paragraphs(text) or [""]
    slides: list[list[str]] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        if current and size + len(block) > 900:
            slides.append(current)
            current, size = [], 0
        # Split very long paragraphs so nothing overflows a slide.
        pieces = [block[i:i + 900] for i in range(0, len(block), 900)] or [""]
        for piece in pieces:
            if current and size + len(piece) > 900:
                slides.append(current)
                current, size = [], 0
            current.append(piece)
            size += len(piece)
    if current:
        slides.append(current)
    for number, group in enumerate(slides, start=1):
        slide = presentation.slides.add_slide(presentation.slide_layouts[5])
        slide.shapes.title.text = title if number == 1 else f"{title} ({number})"
        box = slide.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(8.8), Inches(5.2))
        frame = box.text_frame
        frame.word_wrap = True
        for index, piece in enumerate(group):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.text = piece
            paragraph.font.size = Pt(16)
    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def _html(text: str, title: str) -> bytes:
    body = "".join(f"<p>{html_escape(block).replace(chr(10), '<br>')}</p>" for block in _paragraphs(text))
    page = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{html_escape(title)}</title>"
        "<style>body{font-family:system-ui,'Noto Sans',sans-serif;max-width:46rem;margin:2rem auto;line-height:1.6}</style>"
        f"</head><body><h1>{html_escape(title)}</h1>{body}</body></html>"
    )
    return page.encode("utf-8")


def export_text(text: str, title: str | None, output_format: str) -> tuple[bytes, str, str]:
    output_format = (output_format or "").lower().lstrip(".")
    if output_format not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"Unsupported export format. Choose one of: {', '.join(SUPPORTED_FORMATS)}.")
    if not text or not text.strip():
        raise HTTPException(400, "There is no text to export.")
    if len(text) > MAX_CHARS:
        raise HTTPException(413, "The text is too long to export.")
    stem = safe_stem(title)
    heading = (title or stem).strip()[:120] or stem
    if output_format in {"txt", "md"}:
        data = text.encode("utf-8")
    elif output_format == "html":
        data = _html(text, heading)
    elif output_format == "docx":
        data = _docx(text, heading)
    elif output_format == "pdf":
        data = _text_to_pdf(text)
    elif output_format == "rtf":
        data = _rtf(text)
    elif output_format == "pptx":
        data = _pptx(text, heading)
    else:
        data = json.dumps({"title": heading, "text": text}, ensure_ascii=False, indent=2).encode("utf-8")
    return data, MEDIA_TYPES[output_format], f"{stem}.{output_format}"
