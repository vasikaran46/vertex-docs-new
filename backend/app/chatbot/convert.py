import io
import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import docx.shared
from docx import Document as WordDocument
from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from PIL import Image, UnidentifiedImageError
from pptx import Presentation as PowerPointPresentation
from pptx.util import Inches as PowerPointInches, Pt as PowerPointPt
import pymupdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..conversion_service import (
    _dominant_script,
    _fallback_text_to_pdf,
    _image_to_pdf,
    _libreoffice_convert,
    _open_pdf,
    _pdf_to_docx as cs_pdf_to_docx,
    _pdf_to_images,
    _reportlab_font,
)
from ..models import Document
from ..storage_service import upload_document

logger = logging.getLogger(__name__)

STORAGE_ENV = os.getenv("STORAGE_DIR", "").strip()
DOCUMENTS_STORE = Path(STORAGE_ENV).resolve() if STORAGE_ENV else Path(__file__).resolve().parents[2] / "storage"
DOCUMENTS_STORE.mkdir(parents=True, exist_ok=True)

# Register Windows Unicode fonts for ReportLab if available
for font_name, font_file in [("Arial", "C:/Windows/Fonts/arial.ttf"), ("SegoeUI", "C:/Windows/Fonts/segoeui.ttf")]:
    if os.path.exists(font_file):
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_file))
        except Exception:
            pass


def is_libreoffice_available() -> bool:
    """Check if LibreOffice executable is accessible."""
    configured = os.getenv("LIBREOFFICE_PATH", "").strip()
    if configured and Path(configured).is_file():
        return True
    if shutil.which("soffice") or shutil.which("libreoffice"):
        return True
    for candidate in [
        Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "LibreOffice" / "program" / "soffice.exe",
        Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "LibreOffice" / "program" / "soffice.exe",
    ]:
        if candidate.is_file():
            return True
    return False


MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "application/zip",
    "zip": "application/zip",
}

FORMAT_LABELS = {
    "pdf": "PDF Document",
    "docx": "Word Document (DOCX)",
    "txt": "Plain Text (TXT)",
    "pptx": "PowerPoint Presentation (PPTX)",
    "xlsx": "Excel Spreadsheet (XLSX)",
    "png": "Images (PNG ZIP)",
}

APPROXIMATE_FORMATS = {"pptx", "xlsx"}


# ============================================================================
# CONVERTER FUNCTIONS: (data: bytes, source_filename: str) -> (bytes, str, bool)
# ============================================================================

def docx_to_pdf(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        doc = WordDocument(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(400, f"Invalid DOCX file: {e}") from e

    output = io.BytesIO()
    pdf = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()

    # Select best font for Unicode if needed
    full_text = " ".join(p.text for p in doc.paragraphs)
    script = _dominant_script(full_text)
    font_name = _reportlab_font(script) or ("SegoeUI" if "SegoeUI" in pdfmetrics.getRegisteredFontNames() else "Helvetica")

    body_style = ParagraphStyle("DocxBody", parent=styles["Normal"], fontName=font_name)
    h1_style = ParagraphStyle("DocxH1", parent=styles["Heading1"], fontName=font_name)
    h2_style = ParagraphStyle("DocxH2", parent=styles["Heading2"], fontName=font_name)
    h3_style = ParagraphStyle("DocxH3", parent=styles["Heading3"], fontName=font_name)
    title_style = ParagraphStyle("DocxTitle", parent=styles["Title"], fontName=font_name)

    story = []

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            story.append(Spacer(1, 4 * mm))
            continue

        style = body_style
        if p.style and p.style.name:
            style_name = p.style.name.lower()
            if "heading 1" in style_name:
                style = h1_style
            elif "heading 2" in style_name:
                style = h2_style
            elif "heading 3" in style_name:
                style = h3_style
            elif "title" in style_name:
                style = title_style

        story.append(Paragraph(escape(text), style))
        story.append(Spacer(1, 2 * mm))

    for table in doc.tables:
        table_data = []
        for row in table.rows:
            row_cells = [Paragraph(escape(cell.text.strip()), body_style) for cell in row.cells]
            table_data.append(row_cells)
        if table_data:
            t = Table(table_data)
            t.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(t)
            story.append(Spacer(1, 4 * mm))

    if not story:
        story.append(Paragraph("Empty document", body_style))

    try:
        pdf.build(story)
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}") from e

    return output.getvalue(), MEDIA_TYPES["pdf"], False


def docx_to_txt(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        doc = WordDocument(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(400, f"Invalid DOCX file: {e}") from e

    lines = []
    for p in doc.paragraphs:
        lines.append(p.text)

    if doc.tables:
        lines.append("")
        for idx, table in enumerate(doc.tables, start=1):
            lines.append(f"--- Table {idx} ---")
            for row in table.rows:
                row_text = "\t".join(cell.text.strip().replace("\n", " ") for cell in row.cells)
                lines.append(row_text)
            lines.append("")

    content = "\n".join(lines).strip()
    return content.encode("utf-8"), MEDIA_TYPES["txt"], False


def docx_to_pptx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        doc = WordDocument(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(400, f"Invalid DOCX file: {e}") from e

    prs = PowerPointPresentation()
    title_slide_layout = prs.slide_layouts[0]
    bullet_slide_layout = prs.slide_layouts[1]

    current_slide = None
    text_frame = None

    # First slide as title slide
    first_title = Path(filename).stem
    first_slide = prs.slides.add_slide(title_slide_layout)
    first_slide.shapes.title.text = first_title
    if len(first_slide.shapes.placeholders) > 1:
        first_slide.shapes.placeholders[1].text = "Converted from Word Document"

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue

        style_name = (p.style.name if p.style and p.style.name else "").lower()
        is_heading = "heading 1" in style_name or "heading 2" in style_name or "title" in style_name

        if is_heading or current_slide is None:
            current_slide = prs.slides.add_slide(bullet_slide_layout)
            current_slide.shapes.title.text = text
            text_frame = current_slide.shapes.placeholders[1].text_frame
            text_frame.word_wrap = True
        else:
            p_bullet = text_frame.add_paragraph()
            p_bullet.text = text
            p_bullet.level = 0

    if doc.tables and current_slide:
        # Note skipped tables/images
        p_note = text_frame.add_paragraph()
        p_note.text = "[Tables/diagrams summarized from original document]"
        p_note.level = 1

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue(), MEDIA_TYPES["pptx"], True


def docx_to_xlsx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        doc = WordDocument(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(400, f"Invalid DOCX file: {e}") from e

    wb = Workbook()
    if doc.tables:
        for idx, table in enumerate(doc.tables):
            sheet = wb.active if idx == 0 else wb.create_sheet()
            sheet.title = f"Table {idx + 1}"[:31]
            for row in table.rows:
                sheet.append([cell.text.strip() for cell in row.cells])
    else:
        sheet = wb.active
        sheet.title = "Document Content"
        has_content = False
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                sheet.append([text])
                has_content = True
        if not has_content:
            sheet.append(["Empty document"])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), MEDIA_TYPES["xlsx"], True


def pdf_to_images(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    out_bytes = _pdf_to_images(data, "png")
    return out_bytes, MEDIA_TYPES["png"], False


def pdf_to_docx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    doc = _open_pdf(data)
    word = WordDocument()
    try:
        has_text = False
        for index, page in enumerate(doc, start=1):
            if index > 1:
                word.add_page_break()
            text = page.get_text("text").strip()
            word.add_heading(f"Page {index}", level=2)
            if text:
                has_text = True
                for paragraph in text.split("\n\n"):
                    if paragraph.strip():
                        word.add_paragraph(paragraph.strip())
            else:
                word.add_paragraph("[No selectable text on this page - scanned or image content]")
    finally:
        doc.close()

    out = io.BytesIO()
    word.save(out)
    return out.getvalue(), MEDIA_TYPES["docx"], False


def pdf_to_txt(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    doc = _open_pdf(data)
    lines = []
    try:
        for index, page in enumerate(doc, start=1):
            lines.append(f"--- Page {index} ---")
            text = page.get_text("text").strip()
            if text:
                lines.append(text)
            else:
                lines.append("[No selectable text - scanned page]")
            lines.append("")
    finally:
        doc.close()

    content = "\n".join(lines).strip()
    return content.encode("utf-8"), MEDIA_TYPES["txt"], False


def pdf_to_pptx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    doc = _open_pdf(data)
    prs = PowerPointPresentation()
    bullet_layout = prs.slide_layouts[1]
    try:
        for index, page in enumerate(doc, start=1):
            slide = prs.slides.add_slide(bullet_layout)
            slide.shapes.title.text = f"Page {index}"
            text = page.get_text("text").strip()
            tf = slide.shapes.placeholders[1].text_frame
            tf.word_wrap = True
            if text:
                blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
                for b_idx, block in enumerate(blocks[:8]):  # limit lines per slide
                    if b_idx == 0:
                        tf.text = block
                    else:
                        p = tf.add_paragraph()
                        p.text = block
                        p.level = 0
            else:
                tf.text = "[No selectable text on this page]"
    finally:
        doc.close()

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue(), MEDIA_TYPES["pptx"], True


def pdf_to_xlsx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    doc = _open_pdf(data)
    wb = Workbook()
    tables_found = False
    try:
        for index, page in enumerate(doc, start=1):
            tables = page.find_tables().tables
            if tables:
                for t_idx, table in enumerate(tables, start=1):
                    sheet_title = f"P{index}_T{t_idx}"[:31]
                    sheet = wb.active if not tables_found else wb.create_sheet()
                    sheet.title = sheet_title
                    tables_found = True
                    for row in table.extract():
                        sheet.append([cell or "" for cell in row])
        if not tables_found:
            sheet = wb.active
            sheet.title = "Text Lines"
            for page in doc:
                for line in page.get_text("text").splitlines():
                    if line.strip():
                        sheet.append([line.strip()])
    finally:
        doc.close()

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), MEDIA_TYPES["xlsx"], True


def pdf_to_images(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    out_bytes = _pdf_to_images(data, "png")
    return out_bytes, MEDIA_TYPES["png"], False


def txt_to_pdf(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    text = data.decode("utf-8", errors="replace")
    if not text.strip():
        text = "Empty document"
    try:
        out_bytes = _fallback_text_to_pdf(text)
        return out_bytes, MEDIA_TYPES["pdf"], False
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}") from e


def txt_to_docx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    text = data.decode("utf-8", errors="replace")
    word = WordDocument()
    for block in text.split("\n\n"):
        block = block.strip()
        if block:
            word.add_paragraph(block)
    if not text.strip():
        word.add_paragraph("Empty document")
    out = io.BytesIO()
    word.save(out)
    return out.getvalue(), MEDIA_TYPES["docx"], False


def txt_to_pptx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    text = data.decode("utf-8", errors="replace")
    prs = PowerPointPresentation()
    bullet_layout = prs.slide_layouts[1]

    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if not blocks:
        blocks = ["Empty document"]

    for idx, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        slide = prs.slides.add_slide(bullet_layout)
        slide.shapes.title.text = lines[0] if lines else f"Slide {idx}"
        tf = slide.shapes.placeholders[1].text_frame
        tf.word_wrap = True
        body_lines = lines[1:] if len(lines) > 1 else ["[No additional content]"]
        for b_idx, line in enumerate(body_lines):
            if b_idx == 0:
                tf.text = line
            else:
                p = tf.add_paragraph()
                p.text = line
                p.level = 0

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue(), MEDIA_TYPES["pptx"], True


def txt_to_xlsx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    text = data.decode("utf-8", errors="replace")
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Text Data"

    has_rows = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        has_rows = True
        if "\t" in line:
            sheet.append([cell.strip() for cell in line.split("\t")])
        elif "," in line and not line.startswith("#"):
            sheet.append([cell.strip() for cell in line.split(",")])
        else:
            sheet.append([line])

    if not has_rows:
        sheet.append(["Empty document"])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), MEDIA_TYPES["xlsx"], True


def pdf_to_images(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    out_bytes = _pdf_to_images(data, "png")
    return out_bytes, MEDIA_TYPES["png"], False


def pptx_to_pdf(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    if not is_libreoffice_available():
        raise HTTPException(
            503,
            detail={
                "error_code": "ENGINE_MISSING",
                "message": "LibreOffice is required for PPTX to PDF conversion.",
            },
        )
    out_bytes = _libreoffice_convert(data, "pptx", "pdf", "pdf")
    return out_bytes, MEDIA_TYPES["pdf"], False


def pptx_to_txt(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        prs = PowerPointPresentation(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(400, f"Invalid PPTX file: {e}") from e

    lines = []
    for index, slide in enumerate(prs.slides, start=1):
        lines.append(f"--- Slide {index} ---")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    if p.text.strip():
                        lines.append(p.text.strip())
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                lines.append(f"[Notes: {notes}]")
        lines.append("")

    content = "\n".join(lines).strip()
    return content.encode("utf-8"), MEDIA_TYPES["txt"], False


def pptx_to_docx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        prs = PowerPointPresentation(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(400, f"Invalid PPTX file: {e}") from e

    word = WordDocument()
    for index, slide in enumerate(prs.slides, start=1):
        title = ""
        body_lines = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                if shape == slide.shapes.title or (not title and shape.text.strip()):
                    title = shape.text.strip()
                else:
                    for p in shape.text_frame.paragraphs:
                        if p.text.strip():
                            body_lines.append(p.text.strip())
        heading_text = f"Slide {index}: {title}" if title else f"Slide {index}"
        word.add_heading(heading_text, level=2)
        for bl in body_lines:
            word.add_paragraph(bl)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                word.add_paragraph(f"Notes: {notes}")

    out = io.BytesIO()
    word.save(out)
    return out.getvalue(), MEDIA_TYPES["docx"], False


def xlsx_to_pdf(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    if not is_libreoffice_available():
        raise HTTPException(
            503,
            detail={
                "error_code": "ENGINE_MISSING",
                "message": "LibreOffice is required for XLSX to PDF conversion.",
            },
        )
    out_bytes = _libreoffice_convert(data, "xlsx", "pdf", "pdf")
    return out_bytes, MEDIA_TYPES["pdf"], False


def xlsx_to_txt(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True)
    except Exception as e:
        raise HTTPException(400, f"Invalid XLSX file: {e}") from e

    lines = []
    for sheet in wb.worksheets:
        lines.append(f"--- Sheet: {sheet.title} ---")
        for row in sheet.iter_rows(values_only=True):
            row_vals = [str(cell) if cell is not None else "" for cell in row]
            if any(row_vals):
                lines.append("\t".join(row_vals))
        lines.append("")

    content = "\n".join(lines).strip()
    return content.encode("utf-8"), MEDIA_TYPES["txt"], False


def xlsx_to_docx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True)
    except Exception as e:
        raise HTTPException(400, f"Invalid XLSX file: {e}") from e

    word = WordDocument()
    for s_idx, sheet in enumerate(wb.worksheets):
        if s_idx > 0:
            word.add_page_break()
        word.add_heading(f"Sheet: {sheet.title}", level=2)
        rows = list(sheet.iter_rows(values_only=True))
        # Filter trailing blank rows
        while rows and not any(rows[-1]):
            rows.pop()
        if not rows:
            word.add_paragraph("Empty sheet")
            continue

        max_cols = max(len(r) for r in rows)
        table = word.add_table(rows=len(rows), cols=max_cols)
        for r_idx, row in enumerate(rows):
            for c_idx, cell in enumerate(row):
                table.cell(r_idx, c_idx).text = str(cell) if cell is not None else ""

    out = io.BytesIO()
    word.save(out)
    return out.getvalue(), MEDIA_TYPES["docx"], True


def image_to_pdf(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    out_bytes = _image_to_pdf(data)
    return out_bytes, MEDIA_TYPES["pdf"], False


def image_to_docx(data: bytes, filename: str) -> tuple[bytes, str, bool]:
    try:
        with Image.open(io.BytesIO(data)) as img:
            format_name = img.format
            if format_name not in {"PNG", "JPEG", "WEBP", "JPG"}:
                raise ValueError("Unsupported image format")
    except Exception as e:
        raise HTTPException(400, f"Invalid image file: {e}") from e

    word = WordDocument()
    word.add_paragraph(f"Image: {Path(filename).name}")
    try:
        word.add_picture(io.BytesIO(data), width=docx.shared.Inches(5.5))
    except Exception as e:
        raise HTTPException(500, f"Could not insert image into Word document: {e}") from e

    out = io.BytesIO()
    word.save(out)
    return out.getvalue(), MEDIA_TYPES["docx"], False


# ============================================================================
# CONVERTER REGISTRY
# ============================================================================

CONVERTERS: dict[tuple[str, str], Any] = {
    ("docx", "pdf"): docx_to_pdf,
    ("doc", "pdf"): docx_to_pdf,
    ("docx", "txt"): docx_to_txt,
    ("doc", "txt"): docx_to_txt,
    ("docx", "pptx"): docx_to_pptx,
    ("docx", "xlsx"): docx_to_xlsx,

    ("pdf", "docx"): pdf_to_docx,
    ("pdf", "txt"): pdf_to_txt,
    ("pdf", "pptx"): pdf_to_pptx,
    ("pdf", "xlsx"): pdf_to_xlsx,
    ("pdf", "png"): pdf_to_images,
    ("pdf", "zip"): pdf_to_images,

    ("txt", "pdf"): txt_to_pdf,
    ("md", "pdf"): txt_to_pdf,
    ("txt", "docx"): txt_to_docx,
    ("md", "docx"): txt_to_docx,
    ("txt", "pptx"): txt_to_pptx,
    ("md", "pptx"): txt_to_pptx,
    ("txt", "xlsx"): txt_to_xlsx,
    ("md", "xlsx"): txt_to_xlsx,

    ("pptx", "pdf"): pptx_to_pdf,
    ("pptx", "txt"): pptx_to_txt,
    ("ppt", "txt"): pptx_to_txt,
    ("pptx", "docx"): pptx_to_docx,
    ("ppt", "docx"): pptx_to_docx,

    ("xlsx", "pdf"): xlsx_to_pdf,
    ("xlsx", "txt"): xlsx_to_txt,
    ("xls", "txt"): xlsx_to_txt,
    ("xlsx", "docx"): xlsx_to_docx,
    ("xls", "docx"): xlsx_to_docx,

    ("png", "pdf"): image_to_pdf,
    ("jpg", "pdf"): image_to_pdf,
    ("jpeg", "pdf"): image_to_pdf,
    ("webp", "pdf"): image_to_pdf,

    ("png", "docx"): image_to_docx,
    ("jpg", "docx"): image_to_docx,
    ("jpeg", "docx"): image_to_docx,
    ("webp", "docx"): image_to_docx,
}

SUPPORTED_CONVERSIONS = {
    pair: f"{pair[0].upper()} to {pair[1].upper()}" for pair in CONVERTERS
}


def get_conversion_options(source_extension: str) -> list[dict[str, Any]]:
    """Returns valid target formats for this file extension."""
    src = source_extension.lstrip(".").lower()
    has_lo = is_libreoffice_available()

    options = []
    # Candidate target formats in logical display order
    order = ["pdf", "docx", "txt", "pptx", "xlsx", "png"]

    for tgt in order:
        if tgt == src:
            continue
        pair = (src, tgt)
        if pair in CONVERTERS:
            label = f"Convert to {tgt.upper()}"
            if tgt == "png":
                label = "Convert to Images (PNG ZIP)"
            # Check availability
            if (src in {"pptx", "xlsx"} and tgt == "pdf") and not has_lo:
                options.append({
                    "format": tgt,
                    "label": label,
                    "available": False,
                    "approximate": False,
                    "note": "Requires LibreOffice engine on server",
                })
            else:
                is_approx = tgt in APPROXIMATE_FORMATS or (src == "xlsx" and tgt == "docx")
                options.append({
                    "format": tgt,
                    "label": label,
                    "available": True,
                    "approximate": is_approx,
                    "note": "Layout is approximate - review the result." if is_approx else "",
                })

    return options


class ConversionResult(tuple):
    """A 3-tuple (out_bytes, media_type, out_filename) with .approximate attribute for backward compatibility."""

    def __new__(cls, out_bytes: bytes, media_type: str, out_filename: str, approximate: bool = False):
        obj = super().__new__(cls, (out_bytes, media_type, out_filename))
        obj.approximate = approximate
        return obj

    @property
    def out_bytes(self) -> bytes:
        return self[0]

    @property
    def media_type(self) -> str:
        return self[1]

    @property
    def out_filename(self) -> str:
        return self[2]


def run_chatbot_conversion(
    data: bytes,
    source_filename: str,
    target_format: str,
) -> ConversionResult:
    """
    Executes conversion using the central registry.
    Returns ConversionResult (out_bytes, media_type, output_filename) with .approximate boolean.
    """
    src_ext = Path(source_filename).suffix.lstrip(".").lower()
    tgt = target_format.lower().strip()
    if tgt == "text":
        tgt = "txt"
    if tgt == "word":
        tgt = "docx"
    if tgt in {"excel", "spreadsheet", "sheets"}:
        tgt = "xlsx"
    if tgt in {"powerpoint", "ppt", "slides"}:
        tgt = "pptx"

    if src_ext == tgt and tgt in MEDIA_TYPES:
        return ConversionResult(data, MEDIA_TYPES[tgt], f"{Path(source_filename).stem}.{tgt}", False)

    converter = CONVERTERS.get((src_ext, tgt))
    if not converter:
        raise HTTPException(
            415,
            f"Converting from .{src_ext} to {tgt.upper()} is not currently supported (Coming soon).",
        )

    out_bytes, media_type, approximate = converter(data, source_filename)
    base_name = Path(source_filename).stem
    if media_type == "application/zip":
        out_filename = f"{base_name}.zip"
    else:
        out_filename = f"{base_name}.{tgt}"

    return ConversionResult(out_bytes, media_type, out_filename, approximate)


def get_unique_filename(db: Session, owner_id: int, desired_name: str) -> str:
    stem = Path(desired_name).stem
    ext = Path(desired_name).suffix.lower()

    existing_docs = (
        db.query(Document.original_name)
        .filter(Document.owner_id == owner_id, Document.original_name.ilike(f"{stem}%{ext}"))
        .all()
    )
    existing = {doc[0].lower() for doc in existing_docs if doc[0]}

    candidate = f"{stem}{ext}"
    if candidate.lower() not in existing:
        return candidate

    idx = 1
    while f"{stem} ({idx}){ext}".lower() in existing:
        idx += 1
    return f"{stem} ({idx}){ext}"


def save_converted_document_for_user(
    out_bytes: bytes,
    out_filename: str,
    media_type: str,
    owner_id: int,
    db: Session,
) -> Document:
    unique_name = get_unique_filename(db, owner_id, out_filename)
    stored = uuid.uuid4().hex + Path(unique_name).suffix.lower()
    upload_document(stored, out_bytes, media_type)

    doc = Document(
        owner_id=owner_id,
        original_name=unique_name,
        stored_name=stored,
        content_type=media_type,
        size=len(out_bytes),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def detect_conversion_intent(message: str) -> str | None:
    msg = message.lower()
    patterns = [
        r"(?:convert|change|transform|export|save)(?:\s+this)?(?:\s+document|\s+file|\s+it)?\s+(?:in\s+to|into|to|as)\s+(pdf|docx|txt|text|doc|pptx|ppt|xlsx|excel|slides)",
        r"(?:give|make)\s+me\s+a\s+(pdf|docx|txt|pptx|xlsx|excel|word)\s+version",
        r"\bconvert\s+(pdf|docx|txt|pptx|xlsx)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, msg)
        if match:
            target = match.group(1).lower()
            if target in {"text", "plain"}:
                return "txt"
            if target in {"word", "doc"}:
                return "docx"
            if target in {"excel", "sheets", "spreadsheet"}:
                return "xlsx"
            if target in {"powerpoint", "ppt", "slides"}:
                return "pptx"
            return target
    return None
