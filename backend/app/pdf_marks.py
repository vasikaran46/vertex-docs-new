"""Burn annotations and signature stamps into PDFs (business logic, no HTTP)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pymupdf

FONT_DIRECTORY = Path(__file__).resolve().parent / "assets" / "fonts"
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
ANNOTATION_TYPES = {"highlight", "text", "pen", "rect"}
MAX_ANNOTATIONS = 2000
MAX_POINTS = 4000


class AnnotationError(ValueError):
    pass


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _unit(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnnotationError(f"{name} must be a number")
    if not 0 <= float(value) <= 1:
        raise AnnotationError(f"{name} must be between 0 and 1")
    return float(value)


def validate_annotations(items) -> list[dict]:
    """Return a sanitized copy of the annotation list or raise AnnotationError."""
    if not isinstance(items, list):
        raise AnnotationError("annotations must be a list")
    if len(items) > MAX_ANNOTATIONS:
        raise AnnotationError(f"At most {MAX_ANNOTATIONS} annotations are supported")
    clean: list[dict] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AnnotationError(f"annotation {index + 1} is invalid")
        kind = item.get("type")
        if kind not in ANNOTATION_TYPES:
            raise AnnotationError(f"annotation {index + 1} has an unsupported type")
        page = item.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1 or page > 5000:
            raise AnnotationError(f"annotation {index + 1} has an invalid page")
        color = item.get("color", "#ffe066")
        if not isinstance(color, str) or not _COLOR.match(color):
            raise AnnotationError(f"annotation {index + 1} has an invalid colour")
        entry: dict = {"id": str(item.get("id", index))[:40], "type": kind, "page": page, "color": color.lower()}
        if kind in {"highlight", "rect", "text"}:
            entry["x"] = _unit(item.get("x"), "x")
            entry["y"] = _unit(item.get("y"), "y")
        if kind in {"highlight", "rect"}:
            entry["w"] = _unit(item.get("w"), "w")
            entry["h"] = _unit(item.get("h"), "h")
        if kind == "text":
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise AnnotationError(f"annotation {index + 1} needs text")
            entry["text"] = text[:2000]
            size = item.get("size", 12)
            if isinstance(size, bool) or not isinstance(size, (int, float)) or not 4 <= size <= 96:
                raise AnnotationError(f"annotation {index + 1} has an invalid font size")
            entry["size"] = float(size)
        if kind == "pen":
            points = item.get("points")
            if not isinstance(points, list) or len(points) < 2 or len(points) > MAX_POINTS:
                raise AnnotationError(f"annotation {index + 1} needs 2-{MAX_POINTS} points")
            entry["points"] = [
                [_unit(point[0], "point x"), _unit(point[1], "point y")]
                for point in points
                if isinstance(point, (list, tuple)) and len(point) == 2
            ]
            if len(entry["points"]) < 2:
                raise AnnotationError(f"annotation {index + 1} has invalid points")
            width = item.get("width", 2)
            if isinstance(width, bool) or not isinstance(width, (int, float)) or not 0.5 <= width <= 40:
                raise AnnotationError(f"annotation {index + 1} has an invalid stroke width")
            entry["width"] = float(width)
        clean.append(entry)
    return clean


def _font_for(text: str) -> tuple[str, str | None]:
    """Return (fontname, fontfile) able to draw the text."""
    for char in text:
        code = ord(char)
        if 0x0B80 <= code <= 0x0BFF:
            return "NotoTamil", str(FONT_DIRECTORY / "NotoSansTamil-Regular.ttf")
        if 0x0900 <= code <= 0x097F:
            return "NotoDeva", str(FONT_DIRECTORY / "NotoSansDevanagari-Regular.ttf")
    return "helv", None


def apply_annotations(pdf_bytes: bytes, annotations: list[dict]) -> bytes:
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise AnnotationError("The stored file is not a readable PDF") from error
    try:
        if doc.needs_pass:
            raise AnnotationError("Password-protected PDFs cannot be annotated")
        for item in annotations:
            if item["page"] > doc.page_count:
                continue  # annotation belongs to a page that no longer exists
            page = doc[item["page"] - 1]
            width, height = page.rect.width, page.rect.height
            color = _hex_to_rgb(item["color"])
            kind = item["type"]
            if kind in {"highlight", "rect"}:
                rect = pymupdf.Rect(
                    item["x"] * width, item["y"] * height,
                    (item["x"] + item["w"]) * width, (item["y"] + item["h"]) * height,
                )
                if kind == "highlight":
                    annot = page.add_rect_annot(rect)
                    annot.set_colors(stroke=None, fill=color)
                    annot.set_opacity(0.4)
                else:
                    annot = page.add_rect_annot(rect)
                    annot.set_colors(stroke=color, fill=None)
                    annot.set_border(width=1.5)
                annot.update()
            elif kind == "text":
                fontname, fontfile = _font_for(item["text"])
                point = pymupdf.Point(item["x"] * width, item["y"] * height + item["size"])
                kwargs = {"fontsize": item["size"], "color": color, "fontname": fontname}
                if fontfile:
                    kwargs["fontfile"] = fontfile
                page.insert_text(point, item["text"], **kwargs)
            elif kind == "pen":
                points = [pymupdf.Point(px * width, py * height) for px, py in item["points"]]
                shape = page.new_shape()
                shape.draw_polyline(points)
                shape.finish(color=color, fill=None, width=item["width"], closePath=False)
                shape.commit()
        return doc.tobytes(garbage=3, deflate=True)
    finally:
        doc.close()


def stamp_signature(pdf_bytes: bytes, signer_name: str, signature_text: str, request_id: int) -> bytes:
    """Append a visible signature block to the last page and return the new PDF."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise AnnotationError("The document is not a readable PDF") from error
    try:
        if doc.needs_pass or doc.page_count == 0:
            raise AnnotationError("This PDF cannot be signed")
        page = doc[doc.page_count - 1]
        box = pymupdf.Rect(page.rect.width - 270, page.rect.height - 120, page.rect.width - 36, page.rect.height - 40)
        page.draw_rect(box, color=(0.24, 0.52, 0.36), width=1)
        sig_font, sig_file = _font_for(signature_text)
        kwargs = {"fontsize": 20, "color": (0.1, 0.2, 0.45), "fontname": sig_font if sig_file else "tiit"}
        if sig_file:
            kwargs["fontfile"] = sig_file
        page.insert_text(pymupdf.Point(box.x0 + 10, box.y0 + 30), signature_text, **kwargs)
        name_font, name_file = _font_for(signer_name)
        meta_kwargs = {"fontsize": 8, "color": (0.25, 0.25, 0.25), "fontname": name_font}
        if name_file:
            meta_kwargs["fontfile"] = name_file
        stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        page.insert_text(pymupdf.Point(box.x0 + 10, box.y0 + 50), f"Signed by {signer_name}", **meta_kwargs)
        page.insert_text(pymupdf.Point(box.x0 + 10, box.y0 + 62), f"{stamp} · Request #{request_id}", fontsize=8, color=(0.25, 0.25, 0.25), fontname="helv")
        return doc.tobytes(garbage=3, deflate=True)
    finally:
        doc.close()
