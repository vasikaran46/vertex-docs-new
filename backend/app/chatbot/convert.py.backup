import io
import logging
import os
import re
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document as WordDocument
from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..conversion_service import convert_document
from ..models import Document

logger = logging.getLogger(__name__)

STORAGE_ENV = os.getenv("STORAGE_DIR", "").strip()
DOCUMENTS_STORE = Path(STORAGE_ENV).resolve() if STORAGE_ENV else Path(__file__).resolve().parents[2] / "storage"
DOCUMENTS_STORE.mkdir(parents=True, exist_ok=True)

SUPPORTED_CONVERSIONS = {
    ("pdf", "docx"): "PDF to Word (DOCX)",
    ("docx", "pdf"): "Word (DOCX) to PDF",
    ("txt", "pdf"): "Plain Text to PDF",
    ("md", "pdf"): "Markdown to PDF",
    ("pdf", "txt"): "PDF to Text",
    ("jpg", "pdf"): "Image to PDF",
    ("jpeg", "pdf"): "Image to PDF",
    ("png", "pdf"): "Image to PDF",
    ("webp", "pdf"): "Image to PDF",
}


def docx_to_pdf_reportlab(data: bytes) -> bytes:
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
    story = []

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            story.append(Spacer(1, 4 * mm))
            continue

        style = styles["Normal"]
        if p.style and p.style.name:
            style_name = p.style.name.lower()
            if "heading 1" in style_name:
                style = styles["Heading1"]
            elif "heading 2" in style_name:
                style = styles["Heading2"]
            elif "heading 3" in style_name:
                style = styles["Heading3"]
            elif "title" in style_name:
                style = styles["Title"]

        story.append(Paragraph(escape(text), style))
        story.append(Spacer(1, 2 * mm))

    for table in doc.tables:
        table_data = []
        for row in table.rows:
            row_cells = [Paragraph(escape(cell.text.strip()), styles["Normal"]) for cell in row.cells]
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
        story.append(Paragraph("Empty document", styles["Normal"]))

    try:
        pdf.build(story)
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}") from e

    return output.getvalue()


def txt_to_pdf_reportlab(data: bytes) -> bytes:
    text = data.decode("utf-8", errors="replace")
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
    story = []
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed:
            story.append(Spacer(1, 3 * mm))
        else:
            story.append(Paragraph(escape(trimmed), styles["Normal"]))
            story.append(Spacer(1, 1.5 * mm))

    if not story:
        story.append(Paragraph("Empty document", styles["Normal"]))

    try:
        pdf.build(story)
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}") from e

    return output.getvalue()


def run_chatbot_conversion(
    data: bytes,
    source_filename: str,
    target_format: str,
) -> tuple[bytes, str, str]:
    """
    Executes conversion:
    1. For DOCX -> PDF and TXT/MD -> PDF, uses native reportlab renderer.
    2. For other supported formats (PDF -> DOCX, Image -> PDF, PDF -> TXT), delegates to conversion_service.
    """
    src_ext = Path(source_filename).suffix.lstrip(".").lower()
    tgt = target_format.lower().strip()
    if tgt == "text":
        tgt = "txt"

    base_name = Path(source_filename).stem

    if src_ext in {"docx", "doc"} and tgt == "pdf":
        out_bytes = docx_to_pdf_reportlab(data)
        return out_bytes, "application/pdf", f"{base_name}.pdf"

    if src_ext in {"txt", "md"} and tgt == "pdf":
        out_bytes = txt_to_pdf_reportlab(data)
        return out_bytes, "application/pdf", f"{base_name}.pdf"

    # Delegate to existing conversion service for PDF -> DOCX, Image -> PDF, PDF -> TXT
    try:
        out_bytes, media_type, out_filename = convert_document(data, source_filename, tgt)
        return out_bytes, media_type, f"{base_name}.{tgt}"
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Conversion failed: {e}") from e


def save_converted_document_for_user(
    out_bytes: bytes,
    out_filename: str,
    media_type: str,
    owner_id: int,
    db: Session,
) -> Document:
    stored = uuid.uuid4().hex + Path(out_filename).suffix.lower()
    dest = DOCUMENTS_STORE / stored
    dest.write_bytes(out_bytes)

    doc = Document(
        owner_id=owner_id,
        original_name=out_filename,
        stored_name=stored,
        content_type=media_type,
        size=len(out_bytes),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def detect_conversion_intent(message: str) -> str | None:
    """
    Returns detected target format (e.g. 'pdf', 'docx', 'txt') or None.
    """
    msg = message.lower()
    patterns = [
        r"(?:convert|change|transform|export|save)(?:\s+this)?(?:\s+document|\s+file|\s+it)?\s+(?:in)?to\s+(pdf|docx|txt|text|doc)",
        r"(?:give|make)\s+me\s+a\s+(pdf|docx|txt)\s+version",
        r"\bconvert\s+(pdf|docx|txt)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, msg)
        if match:
            target = match.group(1).lower()
            return "txt" if target == "text" else target
    return None
