import base64
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document as WordDocument
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
import pymupdf

<<<<<<< HEAD
=======
from ..ocr import image_text_with_ocr, pdf_text_with_ocr

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
logger = logging.getLogger(__name__)

STORAGE_ENV = os.getenv("STORAGE_DIR", "").strip()
STORE_BASE = Path(STORAGE_ENV).resolve() if STORAGE_ENV else Path(__file__).resolve().parents[2] / "storage"
STORE_DIR = STORE_BASE / "chatbot_attachments"
STORE_DIR.mkdir(parents=True, exist_ok=True)
META_FILE = STORE_DIR / "attachments_metadata.json"

MAX_FILE_BYTES = 50 * 1024 * 1024
CONTEXT_BUDGET_CHARS = 18000
CHUNK_SIZE = 2500

SUPPORTED_DOC_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
SUPPORTED_IMG_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_EXTENSIONS = SUPPORTED_DOC_EXTENSIONS | SUPPORTED_IMG_EXTENSIONS


def _load_meta_db() -> dict[str, dict[str, Any]]:
    if not META_FILE.exists():
        return {}
    try:
        with META_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not read attachment metadata: %s", e)
        return {}


def _save_meta_db(data: dict[str, dict[str, Any]]) -> None:
    try:
        temp_file = META_FILE.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        temp_file.replace(META_FILE)
    except Exception as e:
        logger.error("Could not write attachment metadata: %s", e)


def extract_docx_text(content: bytes) -> str:
    try:
        doc = WordDocument(io.BytesIO(content))
        elements: list[str] = []
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                elements.append(text)
        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    elements.append(" | ".join(row_cells))
        return "\n\n".join(elements)
    except Exception as e:
        raise HTTPException(400, f"Could not read DOCX file: {e}") from e


def extract_pdf_text(content: bytes) -> tuple[str, bool]:
    """Returns (extracted_text, is_scanned)"""
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as e:
        raise HTTPException(400, f"Could not read PDF file: {e}") from e

    pages_text: list[str] = []
    try:
        for page_idx, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages_text.append(f"--- Page {page_idx} ---\n{text}")
    finally:
        doc.close()

    full_text = "\n\n".join(pages_text).strip()
<<<<<<< HEAD
    if not full_text:
        return (
            "OCR not available: this PDF appears to be a scanned image or contains no selectable text. Please upload a document with readable text or convert it first.",
            True,
        )
    return full_text, False
=======
    if full_text:
        return full_text, False

    # No selectable text: fall back to OCR so scanned PDFs still reach the assistant.
    try:
        ocr_text = pdf_text_with_ocr(content).strip()
    except HTTPException as error:
        logger.info("OCR not available for scanned PDF: %s", error.detail)
        ocr_text = ""
    except Exception as error:
        logger.warning("OCR failed for scanned PDF: %s", error)
        ocr_text = ""
    if ocr_text:
        return ocr_text, True
    return (
        "OCR not available: this PDF appears to be a scanned image or contains no selectable text. Please upload a document with readable text or convert it first.",
        True,
    )
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5


def extract_plain_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def extract_image_payload(content: bytes, ext: str) -> str:
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        return base64.b64encode(content).decode("ascii")
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise HTTPException(400, "Attach a valid PNG, JPEG, or WebP image smaller than 4 MB.") from e


def ingest_attachment(
    filename: str,
    content: bytes,
    content_type: str,
    owner_id: int,
    conversation_id: int | None = None,
) -> dict[str, Any]:
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "Files must be 50 MB or smaller.")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(415, f"Unsupported file type '{ext}'. Supported: {allowed_list}")

    attachment_id = uuid.uuid4().hex
    safe_filename = Path(filename).name
    stored_path = STORE_DIR / f"{attachment_id}_{safe_filename}"
    stored_path.write_bytes(content)

    extracted_text = ""
    is_image = False
    is_scanned = False
    image_base64: str | None = None

    if ext in SUPPORTED_DOC_EXTENSIONS:
        if ext == ".docx":
            extracted_text = extract_docx_text(content)
        elif ext == ".pdf":
            extracted_text, is_scanned = extract_pdf_text(content)
        elif ext in {".txt", ".md"}:
            extracted_text = extract_plain_text(content)
    elif ext in SUPPORTED_IMG_EXTENSIONS:
        if len(content) > 4 * 1024 * 1024:
            raise HTTPException(413, "Images must be 4 MB or smaller.")
        is_image = True
        image_base64 = extract_image_payload(content, ext)
<<<<<<< HEAD
=======
        # Keep OCR text as well so non-vision models can still read the image.
        try:
            extracted_text = image_text_with_ocr(content).strip()
        except HTTPException as error:
            logger.info("OCR not available for image attachment: %s", error.detail)
        except Exception as error:
            logger.warning("OCR failed for image attachment: %s", error)
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5

    record = {
        "id": attachment_id,
        "owner_id": owner_id,
        "conversation_id": conversation_id,
        "filename": safe_filename,
        "extension": ext,
        "content_type": content_type or "application/octet-stream",
        "size": len(content),
        "extracted_text": extracted_text,
        "is_image": is_image,
        "is_scanned": is_scanned,
        "has_image_data": bool(image_base64),
        "created_at": datetime.utcnow().isoformat(),
    }

    db = _load_meta_db()
    db[attachment_id] = record
    _save_meta_db(db)

    # Return public record without huge payload
    return {
        "id": attachment_id,
        "filename": safe_filename,
        "size": len(content),
        "extension": ext,
        "content_type": record["content_type"],
        "is_image": is_image,
        "is_scanned": is_scanned,
        "text_preview": (extracted_text[:300] + "...") if extracted_text else "",
        "char_count": len(extracted_text),
    }


def get_attachment(attachment_id: str, owner_id: int) -> dict[str, Any]:
    db = _load_meta_db()
    record = db.get(attachment_id)
    if not record or record.get("owner_id") != owner_id:
        raise HTTPException(404, "Attachment not found.")
    return record


def get_attachment_bytes(attachment_id: str, owner_id: int) -> tuple[bytes, str]:
    record = get_attachment(attachment_id, owner_id)
    path = STORE_DIR / f"{attachment_id}_{record['filename']}"
    if not path.is_file():
        raise HTTPException(404, "Attachment file missing from storage.")
    return path.read_bytes(), record["filename"]


def get_conversation_attachments(conversation_id: int, owner_id: int) -> list[dict[str, Any]]:
    db = _load_meta_db()
    results = []
    for record in db.values():
        if record.get("conversation_id") == conversation_id and record.get("owner_id") == owner_id:
            results.append(record)
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results


def link_attachment_to_conversation(attachment_id: str, conversation_id: int, owner_id: int) -> None:
    db = _load_meta_db()
    if attachment_id in db and db[attachment_id].get("owner_id") == owner_id:
        db[attachment_id]["conversation_id"] = conversation_id
        _save_meta_db(db)


def select_relevant_chunks(text: str, query: str, budget: int = CONTEXT_BUDGET_CHARS) -> str:
    """Select the most relevant content if text exceeds budget."""
    if len(text) <= budget:
        return text

    words = re.findall(r"\w{3,}", query.lower())
    chunks = [text[i : i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

    if not words or len(chunks) <= 3:
        truncated = text[:budget]
        return f"{truncated}\n\n[Note: Document was truncated to fit context budget (showing {budget:,} of {len(text):,} characters).]"

    # Score chunks by keyword matches
    scored = []
    for idx, chunk in enumerate(chunks):
        chunk_lower = chunk.lower()
        score = sum(chunk_lower.count(w) for w in words)
        # Give first and last chunk extra baseline weight for overall context
        if idx == 0:
            score += 2
        elif idx == len(chunks) - 1:
            score += 1
        scored.append((score, idx, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    selected_chunks: list[tuple[int, str]] = []
    current_chars = 0
    for _, idx, chunk in scored:
        if current_chars + len(chunk) > budget - 300:
            break
        selected_chunks.append((idx, chunk))
        current_chars += len(chunk)

    selected_chunks.sort(key=lambda x: x[0])
    combined = "\n\n[...]\n\n".join(chunk for _, chunk in selected_chunks)
    return f"{combined}\n\n[Note: Document was summarized with key sections to fit context budget ({current_chars:,} of {len(text):,} characters selected).]"


def build_system_prompt(reply_language: str = "en") -> str:
    lang_desc = (
        "Tanglish (spoken Tamil in Latin letters mixed with common English words)"
        if reply_language == "tanglish"
        else reply_language
    )
    return (
        "You are Vertex Assistant. When document content is provided, answer from it only "
        "and never say you cannot read files. If no document is attached and the user refers to one, "
        f"ask them to attach it. Reply in {lang_desc} where possible. "
        "Format your responses cleanly with Markdown (headings, bullet points, bold key terms) "
        "and never claim an operation succeeded unless confirmed."
    )


def format_chat_prompt(
    user_message: str,
    attachment_records: list[dict[str, Any]],
    query: str,
) -> tuple[str | list[dict[str, Any]], list[str]]:
    """
    Builds the model prompt as:
    DOCUMENT CONTENT (filename): <extracted text>
    USER QUESTION: <user question>
    Also supports multimodal vision parts if an image is attached.
    """
    doc_sections: list[str] = []
    attached_names: list[str] = []
    has_image = False
    image_parts: list[dict[str, Any]] = []

    for att in attachment_records:
        name = att.get("filename", "document")
        attached_names.append(name)
        if att.get("is_image"):
            has_image = True
            ext = att.get("extension", ".png").lstrip(".")
            mime = att.get("content_type", f"image/{ext}")
            path = STORE_DIR / f"{att['id']}_{name}"
            if path.is_file():
                b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
        else:
            raw_text = att.get("extracted_text", "").strip()
            if raw_text:
                selected_text = select_relevant_chunks(raw_text, query)
                doc_sections.append(f"DOCUMENT CONTENT ({name}):\n{selected_text}")

    content_header = "\n\n====================\n\n".join(doc_sections)
    if content_header:
        full_text_prompt = f"{content_header}\n\n====================\n\nUSER QUESTION:\n{user_message}"
    else:
        full_text_prompt = user_message

    if has_image:
        multimodal_content: list[dict[str, Any]] = [{"type": "text", "text": full_text_prompt}]
        multimodal_content.extend(image_parts)
        return multimodal_content, attached_names

    return full_text_prompt, attached_names
