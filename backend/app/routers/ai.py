import asyncio
import base64
import binascii
import io
import json
import logging
import os
<<<<<<< HEAD
import xml.etree.ElementTree as ET
=======
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import httpx
<<<<<<< HEAD
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AssistantConversation, AssistantMessage, Document
from ..schemas import ChatIn, DocumentChatIn, DocumentLanguageIn, DocumentTranslationIn, TranslationIn
from ..security import current_user
=======
from docx import Document as WordDocument
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import load_workbook
from PIL import Image, UnidentifiedImageError
from pptx import Presentation as PowerPointPresentation
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..conversion_service import (
    MAX_ZIP_ENTRIES,
    _decode_text,
    _epub_text,
    _html_text,
    _libreoffice_convert,
    _pages_preview,
)
from ..database import get_db
from ..activity import record_activity
from ..doc_retrieval import extractive_answer, relevant_context
from ..extractive_summary import summarize
from ..humanizer import clean_model_output, humanize_local, looks_non_english
from ..models import AssistantConversation, AssistantMessage, Document
from ..ocr import image_text_with_ocr, pdf_text_with_ocr
from ..translation_quality import build_system_message, leftover_ratio, needs_retry
from ..translation_engine import ProviderFailed, translate_with_providers
from ..schemas import ChatIn, DocumentChatIn, DocumentLanguageIn, DocumentTranslationIn, HumanizeIn, TranslationIn
from ..security import current_user
from ..storage_service import read_document
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
from ..chatbot.attachments import (
    ingest_attachment,
    get_attachment,
    get_attachment_bytes,
    get_conversation_attachments,
    link_attachment_to_conversation,
    build_system_prompt,
    format_chat_prompt,
)
from ..chatbot.convert import (
    run_chatbot_conversion,
    save_converted_document_for_user,
    detect_conversion_intent,
    SUPPORTED_CONVERSIONS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI"])
STORE = Path(__file__).resolve().parents[2] / "storage"
<<<<<<< HEAD
=======
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5

LANGUAGE_NAMES = {
    "en": "English",
    "ta": "Tamil",
    "hi": "Hindi",
    "ml": "Malayalam",
    "te": "Telugu",
    "kn": "Kannada",
    "ja": "Japanese",
    "de": "German",
    "sa": "Sanskrit",
    "bn": "Bengali",
    "fr": "French",
    "es": "Spanish",
    "tanglish": "Tanglish",
}
SOURCE_LANGUAGES = {"auto", *LANGUAGE_NAMES}
MAX_TEXT_CHARS = 20000
TRANSLATION_CHUNK_CHARS = 4000
TRANSLATION_CONCURRENCY = 4
<<<<<<< HEAD
=======
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
FATAL_STATUS_CODES = {401, 402, 403, 404}
RETRY_DELAY_SECONDS = 1.2
FREE_FALLBACK_MODELS = ["inclusionai/ling-3.2-flash:free", "google/gemma-4-31b-it:free"]
SCRIPT_LANGUAGE_RANGES = {
    "ta": (0x0B80, 0x0BFF),
    "hi": (0x0900, 0x097F),
    "bn": (0x0980, 0x09FF),
    "ml": (0x0D00, 0x0D7F),
    "te": (0x0C00, 0x0C7F),
    "kn": (0x0C80, 0x0CFF),
}
MIN_DETECTION_LETTERS = 20

TEXT_EXTENSIONS = {".txt", ".md", ".csv"}
HTML_EXTENSIONS = {".html", ".htm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
LIBREOFFICE_EXTENSIONS = {".doc", ".ppt", ".xls", ".odt", ".ods", ".odp", ".rtf", ".hwp", ".pages"}
READABLE_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".epub", ".zip", *TEXT_EXTENSIONS,
    *HTML_EXTENSIONS, *IMAGE_EXTENSIONS, *LIBREOFFICE_EXTENSIONS,
}
MAX_ZIP_TEXT_BYTES = 50 * 1024 * 1024
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5


class RenameConversationIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ChatStreamIn(BaseModel):
    message: str = Field(default="", max_length=12000)
    language: Literal["en", "ta", "hi", "ml", "te", "kn", "ja", "de", "sa", "bn", "fr", "es", "tanglish"] = "en"
    conversation_id: int | None = None
    attachment_ids: list[str] = Field(default_factory=list)
    context: str | None = Field(default=None, max_length=20000)


<<<<<<< HEAD
def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    try:
        if extension == ".pdf":
            reader = PdfReader(io.BytesIO(content))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        elif extension == ".docx":
            from docx import Document as WordDoc
            try:
                word_doc = WordDoc(io.BytesIO(content))
                text = "\n".join(p.text for p in word_doc.paragraphs if p.text.strip())
            except Exception:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    root = ET.fromstring(archive.read("word/document.xml"))
                namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                paragraphs = ["".join(node.itertext()) for node in root.findall(".//w:p", namespace)]
                text = "\n".join(paragraphs)
        elif extension in {".txt", ".md"}:
            text = content.decode("utf-8-sig")
        else:
            raise HTTPException(415, "Use a PDF, DOCX, TXT, or Markdown document")
    except HTTPException:
        raise
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as e:
        raise HTTPException(400, f"The document could not be read: {e}") from e
    if not text.strip():
        raise HTTPException(400, "No readable text was found in the document")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(413, "The extracted text is over the 20,000 character AI limit")
=======
def detect_document_language(text: str) -> str | None:
    sample = text[:MAX_TEXT_CHARS]
    counts = {code: 0 for code in SCRIPT_LANGUAGE_RANGES}
    latin = 0
    for character in sample:
        if not character.isalpha():
            continue
        point = ord(character)
        for code, (start, end) in SCRIPT_LANGUAGE_RANGES.items():
            if start <= point <= end:
                counts[code] += 1
                break
        else:
            if point <= 0x024F or 0x1E00 <= point <= 0x1EFF:
                latin += 1
    indic_code, indic_count = max(counts.items(), key=lambda item: item[1])
    total = indic_count + latin
    if total < MIN_DETECTION_LETTERS:
        return None
    if indic_count and indic_count >= latin:
        return indic_code
    if latin / total >= 0.6:
        return "en"
    if indic_count / total >= 0.3:
        return indic_code
    return None


def summary_language(text: str, requested: str) -> tuple[str, bool]:
    if requested == "tanglish":
        return "tanglish", False
    detected = detect_document_language(text)
    if detected:
        return detected, False
    return requested, True


def docx_text(content: bytes) -> str:
    word = WordDocument(io.BytesIO(content))
    parts = [paragraph.text for paragraph in word.paragraphs]
    for table in word.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(part for part in parts if part.strip())


def xlsx_text(content: bytes) -> str:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    parts = []
    try:
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                values = [str(value).strip() for value in row if value is not None and str(value).strip()]
                if values:
                    parts.append(" | ".join(values))
    finally:
        workbook.close()
    return "\n".join(parts)


def pptx_text(content: bytes) -> str:
    presentation = PowerPointPresentation(io.BytesIO(content))
    parts = []
    for index, slide in enumerate(presentation.slides, start=1):
        slide_parts = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
                slide_parts.append(shape.text_frame.text.strip())
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        slide_parts.append(" | ".join(cells))
        if slide_parts:
            parts.append(f"Slide {index}\n" + "\n".join(slide_parts))
    return "\n\n".join(parts)


def office_text(content: bytes, extension: str) -> str:
    source = extension.lstrip(".")
    if extension == ".pages":
        preview = _pages_preview(content)
        if preview:
            text = pdf_text_with_ocr(preview)
            if text.strip():
                return text
    if extension in {".ppt", ".xls", ".ods", ".odp"}:
        # These filters do not export to plain text; render them to PDF instead.
        return pdf_text_with_ocr(_libreoffice_convert(content, source, "pdf", "pdf"))
    try:
        converted = _libreoffice_convert(content, source, "txt:Text", "txt")
        return _decode_text(converted)
    except HTTPException as error:
        if error.status_code == 503:
            raise
    pdf = _libreoffice_convert(content, source, "pdf", "pdf")
    return pdf_text_with_ocr(pdf)


def zip_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()][:MAX_ZIP_ENTRIES]
            parts = []
            total = 0
            for member in members:
                extension = Path(member.filename).suffix.lower()
                if extension not in READABLE_EXTENSIONS - {".zip"}:
                    continue
                if member.file_size > MAX_ZIP_TEXT_BYTES:
                    continue
                total += member.file_size
                if total > MAX_ZIP_TEXT_BYTES:
                    break
                try:
                    member_text = extract_extension_text(extension, archive.read(member))
                except HTTPException as error:
                    if error.status_code == 503 and extension in IMAGE_EXTENSIONS:
                        continue
                    raise
                if member_text.strip():
                    parts.append(f"{Path(member.filename).name}\n{member_text}")
    except zipfile.BadZipFile as error:
        raise HTTPException(400, "The uploaded ZIP archive is invalid.") from error
    return "\n\n".join(parts)


def extract_extension_text(extension: str, content: bytes) -> str:
    if extension == ".pdf":
        return pdf_text_with_ocr(content)
    if extension == ".docx":
        return docx_text(content)
    if extension == ".xlsx":
        return xlsx_text(content)
    if extension == ".pptx":
        return pptx_text(content)
    if extension in TEXT_EXTENSIONS:
        return _decode_text(content)
    if extension in HTML_EXTENSIONS:
        return _html_text(content)
    if extension == ".epub":
        return _epub_text(content)
    if extension == ".zip":
        return zip_text(content)
    if extension in IMAGE_EXTENSIONS:
        return image_text_with_ocr(content)
    if extension in LIBREOFFICE_EXTENSIONS:
        return office_text(content, extension)
    supported = ", ".join(sorted(READABLE_EXTENSIONS))
    raise HTTPException(415, f"Use a supported document or image: {supported}")


def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    try:
        text = extract_extension_text(extension, content)
    except HTTPException:
        raise
    except Exception as error:
        logger.warning("Could not extract text from %s: %s", extension, error)
        raise HTTPException(400, "The document could not be read") from error
    text = text.strip()
    if not text:
        raise HTTPException(400, "No readable text was found in the document")
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS].rsplit(" ", 1)[0]
    return text


_TEXT_CACHE: dict[str, str] = {}
_TEXT_CACHE_LIMIT = 48


def _load_document_text(stored_name: str, original_name: str) -> str:
    """Read + extract a stored file. Stored names are unique and files are immutable, so results can be cached."""
    cached = _TEXT_CACHE.get(stored_name)
    if cached is not None:
        return cached
    try:
        content = read_document(stored_name)
    except FileNotFoundError:
        raise HTTPException(404, "Document file is no longer available")
    except Exception:
        logger.exception("Could not read document from storage")
        raise HTTPException(500, "The document could not be opened")
    text = extract_text(original_name, content)
    if len(_TEXT_CACHE) >= _TEXT_CACHE_LIMIT:
        _TEXT_CACHE.pop(next(iter(_TEXT_CACHE)))
    _TEXT_CACHE[stored_name] = text
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return text


def owned_document_text(doc_id: int, db: Session, u) -> str:
    item = db.query(Document).filter_by(id=doc_id, owner_id=u.id).first()
    if not item:
        raise HTTPException(404, "Document not found")
<<<<<<< HEAD
    path = STORE / item.stored_name
    try:
        content = path.read_bytes()
    except OSError:
        raise HTTPException(500, "The document could not be opened")
    return extract_text(item.original_name, content)


async def ai_completion(messages: list[dict]) -> str:
    key = os.getenv("LLM_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Add LLM_API_KEY to backend/.env")
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                base + "/chat/completions",
                headers={"Authorization": "Bearer " + key},
                json={"model": model, "messages": messages},
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as error:
        err_msg = f"AI provider returned {error.response.status_code}: {error.response.text[:200]}"
        logger.error(err_msg)
        raise HTTPException(502, err_msg) from error
    except (httpx.RequestError, KeyError, ValueError, TypeError) as error:
        logger.error("AI completion error: %s", error)
        raise HTTPException(502, f"AI provider request failed: {error}") from error


async def translate_text(x: TranslationIn):
    source = LANGUAGE_NAMES.get(x.source_language, "any language")
    target = LANGUAGE_NAMES[x.target_language]
    tanglish_rule = (
        " Use natural spoken Tamil expressed in Latin letters, mixed with common English words; do not use Tamil script."
        if x.target_language == "tanglish"
        else ""
    )
    system_message = f"Translate the user's text into {target}. The source is {source}; if it is auto, identify it. Preserve meaning, names, formatting, and tone. Return only the translation.{tanglish_rule}"
=======
    return _load_document_text(item.stored_name, item.original_name)


async def owned_document_text_async(doc_id: int, db: Session, u) -> str:
    """Same as owned_document_text but runs the (possibly OCR-heavy) extraction off the event loop."""
    item = db.query(Document).filter_by(id=doc_id, owner_id=u.id).first()
    if not item:
        raise HTTPException(404, "Document not found")
    stored_name, original_name = item.stored_name, item.original_name
    return await asyncio.to_thread(_load_document_text, stored_name, original_name)

def env_file_values() -> dict[str, str]:
    """Read backend/.env so edited LLM settings apply without restarting the server."""
    if os.getenv("VERTEX_IGNORE_ENV_FILE"):
        return {}
    try:
        from dotenv import dotenv_values
        values = dotenv_values(ENV_FILE)
    except (ImportError, OSError, ValueError):
        return {}
    return {name: value.strip() for name, value in values.items() if value and value.strip()}


def llm_setting(name: str, default: str = "") -> str:
    return env_file_values().get(name) or os.getenv(name, default).strip() or default


def provider_error_detail(response: httpx.Response, model: str) -> str:
    try:
        error = response.json().get("error") or {}
    except (ValueError, TypeError, AttributeError):
        error = {}
    message = str(error.get("message") or "").strip()
    lower = message.lower()
    if response.status_code == 401:
        return "The AI provider rejected the API key. Check LLM_API_KEY and LLM_BASE_URL in backend/.env."
    if response.status_code == 402 or "credit" in lower or "quota" in lower:
        return "The AI provider account has no credits left. Add credits or use a free model."
    if response.status_code == 429 or "rate limit" in lower or "rate-limited" in lower:
        return "The AI provider is busy right now. Please retry in a moment."
    if response.status_code == 404:
        return f"The AI provider does not know the model '{model}'. Check LLM_MODEL in backend/.env."
    if message:
        return "AI provider request failed: " + message[:300]
    return "AI provider request failed"


def llm_models() -> list[str]:
    configured = [name.strip() for name in llm_setting("LLM_MODEL", "gpt-4o-mini").split(",") if name.strip()]
    if configured and all(name.endswith(":free") for name in configured):
        for fallback in FREE_FALLBACK_MODELS:
            if fallback not in configured:
                configured.append(fallback)
    return configured or ["gpt-4o-mini"]


async def ai_completion(messages: list[dict]) -> str:
    key = llm_setting("LLM_API_KEY")
    if not key:
        raise HTTPException(503, "Add LLM_API_KEY to backend/.env")
    base = llm_setting("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    models = llm_models()
    last_error: httpx.Response | None = None
    last_model = models[0]
    async with httpx.AsyncClient(timeout=90) as client:
        for model in models:
            for attempt in range(2):
                try:
                    response = await client.post(
                        base + "/chat/completions",
                        headers={"Authorization": "Bearer " + key},
                        json={"model": model, "messages": messages},
                    )
                except httpx.RequestError as error:
                    last_error = None
                    if attempt == 0:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    raise HTTPException(502, "Could not reach the AI provider. Check your connection and LLM_BASE_URL.") from error
                if response.status_code < 400:
                    try:
                        return response.json()["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError, ValueError) as error:
                        raise HTTPException(502, "The AI provider returned an unexpected response.") from error
                last_error = response
                last_model = model
                if response.status_code in RETRYABLE_STATUS_CODES and attempt == 0:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                break
            if last_error is not None and last_error.status_code in FATAL_STATUS_CODES:
                break
    if last_error is not None:
        raise HTTPException(502, provider_error_detail(last_error, last_model))
    raise HTTPException(502, "AI provider request failed")


async def translate_text(x: TranslationIn):
    """Translate with the dedicated engines first (Google Cloud / IndicTrans2 / Argos), then the LLM."""
    engine_error = ""
    try:
        engine_result = await translate_with_providers(x.text, x.source_language, x.target_language)
    except ProviderFailed as error:
        engine_result = None
        engine_error = str(error)
    if engine_result is not None:
        response = {
            "translation": engine_result.translation,
            "source_language": x.source_language,
            "target_language": x.target_language,
            "provider": engine_result.provider,
        }
        if engine_result.warnings:
            response["warnings"] = engine_result.warnings
        return response
    try:
        result = await _translate_with_llm(x)
    except HTTPException as error:
        if error.status_code == 503 and not llm_setting("LLM_API_KEY"):
            raise HTTPException(
                503,
                (engine_error + " " if engine_error else "")
                + "No translation provider is available. Add GOOGLE_TRANSLATE_API_KEY (recommended) or set "
                  "TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE=true for local testing in backend/.env.",
            )
        raise
    result["provider"] = "llm"
    return result


async def _translate_with_llm(x: TranslationIn):
    source = LANGUAGE_NAMES.get(x.source_language, "any language")
    target = LANGUAGE_NAMES[x.target_language]
    system_message = build_system_message(source, target, x.target_language)
    strict_message = build_system_message(source, target, x.target_language, strict=True)
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    chunks = []
    start = 0
    while start < len(x.text):
        end = min(start + TRANSLATION_CHUNK_CHARS, len(x.text))
        if end < len(x.text):
            boundary = x.text.rfind("\n\n", start, end)
            if boundary <= start + TRANSLATION_CHUNK_CHARS // 2:
                boundary = x.text.rfind("\n", start, end)
            if boundary <= start + TRANSLATION_CHUNK_CHARS // 2:
                boundary = x.text.rfind(" ", start, end)
            if boundary > start + TRANSLATION_CHUNK_CHARS // 2:
                end = boundary
        chunks.append(x.text[start:end].strip())
        start = end
        while start < len(x.text) and x.text[start].isspace():
            start += 1

    semaphore = asyncio.Semaphore(TRANSLATION_CONCURRENCY)
<<<<<<< HEAD

    async def translate_chunk(chunk: str) -> str:
        async with semaphore:
            return await ai_completion([
                {"role": "system", "content": system_message},
                {"role": "user", "content": chunk},
            ])

    translated = await asyncio.gather(*(translate_chunk(chunk) for chunk in chunks))
    translation = "\n\n".join(part.strip() for part in translated)
    return {"translation": translation, "source_language": x.source_language, "target_language": x.target_language}
=======
    incomplete_chunks = 0

    async def translate_chunk(chunk: str) -> str:
        nonlocal incomplete_chunks
        async with semaphore:
            result = await ai_completion([
                {"role": "system", "content": system_message},
                {"role": "user", "content": chunk},
            ])
            if needs_retry(chunk, result, x.target_language):
                # Mixed-language input: ask once more, explicitly forbidding leftover source text.
                retry = await ai_completion([
                    {"role": "system", "content": strict_message},
                    {"role": "user", "content": chunk},
                ])
                if leftover_ratio(retry, x.target_language) <= leftover_ratio(result, x.target_language):
                    result = retry
                if needs_retry(chunk, result, x.target_language):
                    incomplete_chunks += 1
            return result

    translated = await asyncio.gather(*(translate_chunk(chunk) for chunk in chunks))
    translation = "\n\n".join(part.strip() for part in translated)
    response = {"translation": translation, "source_language": x.source_language, "target_language": x.target_language}
    if incomplete_chunks:
        response["warnings"] = [
            f"{incomplete_chunks} section(s) may still contain text that is not in {target}. "
            f"The current AI model may not translate every language pair reliably; review the result before using it."
        ]
    return response
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5


def owned_conversation(conversation_id: int, db: Session, u) -> AssistantConversation:
    conversation = db.query(AssistantConversation).filter_by(id=conversation_id, owner_id=u.id).first()
    if not conversation:
        raise HTTPException(404, "Chat not found")
    return conversation


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), u = Depends(current_user)):
    items = (
        db.query(AssistantConversation)
        .filter_by(owner_id=u.id)
        .order_by(desc(AssistantConversation.updated_at))
        .limit(50)
        .all()
    )
    return [{"id": item.id, "title": item.title, "updated_at": item.updated_at} for item in items]


@router.post("/conversations")
def create_conversation(db: Session = Depends(get_db), u = Depends(current_user)):
    conversation = AssistantConversation(owner_id=u.id, title="New chat")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return {"id": conversation.id, "title": conversation.title, "updated_at": conversation.updated_at}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db), u = Depends(current_user)):
    conversation = owned_conversation(conversation_id, db, u)
    messages = (
        db.query(AssistantMessage)
        .filter_by(conversation_id=conversation.id)
        .order_by(AssistantMessage.id)
        .all()
    )
    attachments = get_conversation_attachments(conversation.id, u.id)
    att_meta = [
        {
            "id": a["id"],
            "filename": a["filename"],
            "size": a["size"],
            "extension": a["extension"],
            "is_image": a.get("is_image", False),
            "is_scanned": a.get("is_scanned", False),
        }
        for a in attachments
    ]
    return {
        "id": conversation.id,
        "title": conversation.title,
        "attachments": att_meta,
        "messages": [
            {"id": item.id, "role": item.role, "text": item.content, "created_at": item.created_at}
            for item in messages
        ],
    }


@router.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    x: RenameConversationIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
    conversation = owned_conversation(conversation_id, db, u)
    conversation.title = x.title.strip()[:117]
    conversation.updated_at = datetime.utcnow()
    db.commit()
    return {"id": conversation.id, "title": conversation.title}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), u = Depends(current_user)):
    conversation = owned_conversation(conversation_id, db, u)
    db.query(AssistantMessage).filter_by(conversation_id=conversation.id).delete()
    db.delete(conversation)
    db.commit()
    return {"success": True}


# Backwards compatibility endpoint
@router.post("/chat/attachment-text")
async def chat_attachment_text(file: UploadFile = File(...), u = Depends(current_user)):
    limit = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, "File too large")
    text = await asyncio.to_thread(extract_text, file.filename or "", content)
    return {"name": Path(file.filename or "document").name, "text": text[:12000]}


@router.post("/chat/attachments")
async def upload_chat_attachment(
    file: UploadFile = File(...),
    conversation_id: int | None = Form(None),
    u = Depends(current_user),
):
    limit = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, "Files must be 50 MB or smaller.")
    record = ingest_attachment(
        filename=file.filename or "attachment",
        content=content,
        content_type=file.content_type or "application/octet-stream",
        owner_id=u.id,
        conversation_id=conversation_id,
    )
    return record


@router.get("/chat/attachments/{attachment_id}")
def get_chat_attachment_info(attachment_id: str, u = Depends(current_user)):
    record = get_attachment(attachment_id, u.id)
    return {
        "id": record["id"],
        "filename": record["filename"],
        "size": record["size"],
        "extension": record["extension"],
        "content_type": record["content_type"],
        "is_image": record.get("is_image", False),
        "is_scanned": record.get("is_scanned", False),
        "char_count": len(record.get("extracted_text", "")),
        "created_at": record.get("created_at"),
    }


@router.get("/chat/attachments/{attachment_id}/file")
def download_chat_attachment_file(attachment_id: str, u = Depends(current_user)):
    record = get_attachment(attachment_id, u.id)
    content, filename = get_attachment_bytes(attachment_id, u.id)
    return FileResponse(
        io.BytesIO(content),
        filename=filename,
        media_type=record.get("content_type", "application/octet-stream"),
    )


@router.post("/chat/convert")
async def chatbot_convert(
    attachment_id: str = Form(...),
    target_format: str = Form(...),
    conversation_id: int | None = Form(None),
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
    content, filename = get_attachment_bytes(attachment_id, u.id)
    out_bytes, media_type, out_filename = run_chatbot_conversion(content, filename, target_format)
    saved_doc = save_converted_document_for_user(out_bytes, out_filename, media_type, u.id, db)

    card = {
        "id": saved_doc.id,
        "filename": saved_doc.original_name,
        "size": saved_doc.size,
        "content_type": saved_doc.content_type,
        "download_url": f"/api/documents/{saved_doc.id}/download",
    }

    if conversation_id:
        conversation = owned_conversation(conversation_id, db, u)
        db.add(AssistantMessage(
            conversation_id=conversation.id,
            role="assistant",
<<<<<<< HEAD
            content=f"Your {target_format.upper()} conversion of “{filename}” is ready!\n\n[DOWNLOAD_CARD:{json.dumps(card)}]"
=======
            content=f"Your {target_format.upper()} conversion of \u201c{filename}\u201d is ready!\n\n[DOWNLOAD_CARD:{json.dumps(card)}]"
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
        ))
        conversation.updated_at = datetime.utcnow()
        db.commit()

<<<<<<< HEAD
=======
    record_activity(
        u.id,
        "assistant.document_conversion",
        "document",
        saved_doc.id,
        {"output_format": target_format, "output_size_bytes": saved_doc.size, "mode": "conversion"},
    )

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return {
        "status": "success",
        "card": card,
    }


def validated_chat_image(image_data: str, media_type: str) -> str:
    try:
        decoded = base64.b64decode(image_data, validate=True)
        if len(decoded) > 4 * 1024 * 1024:
            raise ValueError()
        image = Image.open(io.BytesIO(decoded))
        expected = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
        if image.format != expected.get(media_type) or image.width * image.height > 20_000_000:
            raise ValueError()
        image.verify()
        return base64.b64encode(decoded).decode("ascii")
    except (binascii.Error, ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise HTTPException(400, "Attach a valid PNG, JPEG, or WebP image smaller than 4 MB") from error


@router.post("/chat")
async def chat(x: ChatIn, db: Session = Depends(get_db), u = Depends(current_user)):
    conversation = (
        owned_conversation(x.conversation_id, db, u)
        if x.conversation_id
        else AssistantConversation(owner_id=u.id, title="New chat")
    )
    if not x.conversation_id:
        db.add(conversation)
        db.flush()

    # Link conversation attachments
    attachments = get_conversation_attachments(conversation.id, u.id)

    # Check natural language conversion intent
    conversion_target = detect_conversion_intent(x.message)
    if conversion_target and attachments:
        target_att = attachments[0]
        content, src_filename = get_attachment_bytes(target_att["id"], u.id)
        try:
            out_bytes, media_type, out_filename = run_chatbot_conversion(content, src_filename, conversion_target)
            saved_doc = save_converted_document_for_user(out_bytes, out_filename, media_type, u.id, db)
            card = {
                "id": saved_doc.id,
                "filename": saved_doc.original_name,
                "size": saved_doc.size,
                "download_url": f"/api/documents/{saved_doc.id}/download",
            }
            reply = f"I've converted **{src_filename}** to **{conversion_target.upper()}** for you!\n\n[DOWNLOAD_CARD:{json.dumps(card)}]"
            db.add(AssistantMessage(conversation_id=conversation.id, role="user", content=x.message))
            db.add(AssistantMessage(conversation_id=conversation.id, role="assistant", content=reply))
            conversation.updated_at = datetime.utcnow()
            db.commit()
<<<<<<< HEAD
=======
            record_activity(u.id, "assistant.conversion", "document", saved_doc.id, {
                "output_format": conversion_target,
                "output_size_bytes": saved_doc.size,
                "mode": "conversion",
            })
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            return {
                "reply": reply,
                "conversation_id": conversation.id,
                "title": conversation.title,
                "download_card": card,
            }
        except Exception as e:
            logger.warning("Conversion intent failed: %s", e)

    system_instruction = build_system_prompt(x.language)
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_instruction}]

    if x.context:
        msgs.append({"role": "system", "content": "Selected context:\n" + x.context})

    # Include recent conversation turns
    previous = (
        db.query(AssistantMessage)
        .filter_by(conversation_id=conversation.id)
        .order_by(desc(AssistantMessage.id))
        .limit(10)
        .all()
    )
    if previous:
        msgs.extend({"role": item.role, "content": item.content} for item in reversed(previous))
    else:
        msgs.extend({"role": turn.role, "content": turn.content} for turn in x.history)

    # Format user prompt with persistent attachment context
    formatted_prompt, attached_names = format_chat_prompt(x.message, attachments, query=x.message)
    if x.image_data and isinstance(formatted_prompt, str):
        encoded = validated_chat_image(x.image_data, x.image_media_type)
        user_content = [
            {"type": "text", "text": formatted_prompt},
            {"type": "image_url", "image_url": {"url": f"data:{x.image_media_type};base64,{encoded}"}},
        ]
    else:
        user_content = formatted_prompt

    msgs.append({"role": "user", "content": user_content})

    reply = await ai_completion(msgs)

    if conversation.title == "New chat":
        clean_title = x.message.strip().split("\n")[0][:45]
<<<<<<< HEAD
        conversation.title = clean_title + ("…" if len(x.message.strip().split("\n")[0]) > 45 else "")
=======
        conversation.title = clean_title + ("\u2026" if len(x.message.strip().split("\n")[0]) > 45 else "")
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    conversation.updated_at = datetime.utcnow()
    db.add(AssistantMessage(conversation_id=conversation.id, role="user", content=x.message))
    db.add(AssistantMessage(conversation_id=conversation.id, role="assistant", content=reply))
    db.commit()
<<<<<<< HEAD
=======
    record_activity(u.id, "assistant.message", "assistant_conversation", conversation.id, {
        "mode": "chat", "language": x.language,
    })
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return {"reply": reply, "conversation_id": conversation.id, "title": conversation.title}


@router.post("/chat/stream")
async def chat_stream(
    x: ChatStreamIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
<<<<<<< HEAD
    key = os.getenv("LLM_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Add LLM_API_KEY to backend/.env")
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
=======
    key = llm_setting("LLM_API_KEY")
    if not key:
        raise HTTPException(503, "Add LLM_API_KEY to backend/.env")
    base = llm_setting("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = llm_models()[0]
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5

    conversation = (
        owned_conversation(x.conversation_id, db, u)
        if x.conversation_id
        else AssistantConversation(owner_id=u.id, title="New chat")
    )
    if not x.conversation_id:
        db.add(conversation)
        db.flush()

    # Link any new attachments to this conversation
    for att_id in x.attachment_ids:
        link_attachment_to_conversation(att_id, conversation.id, u.id)

    attachments = get_conversation_attachments(conversation.id, u.id)

    # Check natural language conversion intent
    conversion_target = detect_conversion_intent(x.message)
    if conversion_target and attachments:
        target_att = attachments[0]
        content, src_filename = get_attachment_bytes(target_att["id"], u.id)
        out_bytes, media_type, out_filename = run_chatbot_conversion(content, src_filename, conversion_target)
        saved_doc = save_converted_document_for_user(out_bytes, out_filename, media_type, u.id, db)
        card = {
            "id": saved_doc.id,
            "filename": saved_doc.original_name,
            "size": saved_doc.size,
            "download_url": f"/api/documents/{saved_doc.id}/download",
        }
        reply = f"I've converted **{src_filename}** to **{conversion_target.upper()}** for you!\n\n[DOWNLOAD_CARD:{json.dumps(card)}]"
        db.add(AssistantMessage(conversation_id=conversation.id, role="user", content=x.message))
        db.add(AssistantMessage(conversation_id=conversation.id, role="assistant", content=reply))
        conversation.updated_at = datetime.utcnow()
        db.commit()

        async def stream_conversion_card():
<<<<<<< HEAD
=======
            record_activity(u.id, "assistant.conversion", "document", saved_doc.id, {
                "output_format": conversion_target,
                "output_size_bytes": saved_doc.size,
                "mode": "conversion", "streamed": True,
            })
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            yield f"data: {json.dumps({'token': reply})}\n\n"
            yield f"data: {json.dumps({'done': True, 'reply': reply, 'conversation_id': conversation.id, 'title': conversation.title, 'download_card': card})}\n\n"

        return StreamingResponse(stream_conversion_card(), media_type="text/event-stream")

    system_instruction = build_system_prompt(x.language)
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_instruction}]

    if x.context:
        msgs.append({"role": "system", "content": "Selected context:\n" + x.context})

    previous = (
        db.query(AssistantMessage)
        .filter_by(conversation_id=conversation.id)
        .order_by(desc(AssistantMessage.id))
        .limit(10)
        .all()
    )
    if previous:
        msgs.extend({"role": item.role, "content": item.content} for item in reversed(previous))

    formatted_prompt, attached_names = format_chat_prompt(x.message, attachments, query=x.message)
    msgs.append({"role": "user", "content": formatted_prompt})

    conversation_id = conversation.id
    user_message = x.message

    async def event_generator():
        collected_tokens = []
        try:
<<<<<<< HEAD
=======
            stream_completed = False
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            async with httpx.AsyncClient(timeout=90) as client:
                async with client.stream(
                    "POST",
                    base + "/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": msgs, "stream": True},
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
<<<<<<< HEAD
                        err = f"AI Provider returned {response.status_code}: {body.decode(errors='replace')[:200]}"
                        yield f"data: {json.dumps({'error': err})}\n\n"
=======
                        detail = provider_error_detail(httpx.Response(response.status_code, content=body), model)
                        yield f"data: {json.dumps({'error': detail})}\n\n"
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            raw_payload = line[6:].strip()
                            if raw_payload == "[DONE]":
<<<<<<< HEAD
=======
                                stream_completed = True
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                                break
                            try:
                                payload = json.loads(raw_payload)
                                delta = payload["choices"][0]["delta"].get("content", "")
                                if delta:
                                    collected_tokens.append(delta)
                                    yield f"data: {json.dumps({'token': delta})}\n\n"
                            except Exception:
                                pass

<<<<<<< HEAD
=======
            if not stream_completed:
                yield f"data: {json.dumps({'error': 'Generation error: AI provider stream ended before completion.'})}\n\n"
                return

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            full_reply = "".join(collected_tokens)
            # Persist to database in new session
            from ..database import SessionLocal
            with SessionLocal() as db_session:
                conv = db_session.query(AssistantConversation).filter_by(id=conversation_id).first()
<<<<<<< HEAD
                if conv:
                    if conv.title == "New chat":
                        clean_title = user_message.strip().split("\n")[0][:45]
                        conv.title = clean_title + ("…" if len(user_message.strip().split("\n")[0]) > 45 else "")
=======
                persisted = False
                if conv:
                    if conv.title == "New chat":
                        clean_title = user_message.strip().split("\n")[0][:45]
                        conv.title = clean_title + ("\u2026" if len(user_message.strip().split("\n")[0]) > 45 else "")
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                    conv.updated_at = datetime.utcnow()
                    db_session.add(AssistantMessage(conversation_id=conv.id, role="user", content=user_message))
                    db_session.add(AssistantMessage(conversation_id=conv.id, role="assistant", content=full_reply))
                    db_session.commit()
                    conv_title = conv.title
<<<<<<< HEAD
                else:
                    conv_title = "Chat"

=======
                    persisted = True
                else:
                    conv_title = "Chat"

            if persisted:
                record_activity(u.id, "assistant.message", "assistant_conversation", conversation_id, {
                    "mode": "stream", "language": x.language, "streamed": True,
                })
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            yield f"data: {json.dumps({'done': True, 'reply': full_reply, 'conversation_id': conversation_id, 'title': conv_title})}\n\n"

        except Exception as e:
            logger.exception("Error in chat_stream generator")
            yield f"data: {json.dumps({'error': f'Generation error: {str(e)}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/documents/{doc_id}/summarize")
async def summarize_document(
    doc_id: int,
    x: DocumentLanguageIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
<<<<<<< HEAD
    text = owned_document_text(doc_id, db, u)
    language = (
        "Tanglish (spoken Tamil written in Latin letters mixed with English)"
        if x.language == "tanglish"
        else LANGUAGE_NAMES[x.language]
    )
    reply = await ai_completion([
        {
            "role": "system",
            "content": f"Summarize the document accurately in {language}. Use Markdown with a brief overview, key points, and any actions or dates. Do not invent details.",
        },
        {"role": "user", "content": text},
    ])
    return {"summary": reply, "language": x.language}
=======
    text = await owned_document_text_async(doc_id, db, u)
    language_code, used_fallback = summary_language(text, x.language)
    summary = await asyncio.to_thread(summarize, text)
    if not summary.strip():
        raise HTTPException(400, "No readable text was found in the document")
    if x.language != "en":
        try:
            translated = await translate_text(TranslationIn(text=summary, source_language="auto", target_language=x.language))
            if translated and translated.get("translation"):
                summary = translated["translation"]
                language_code = x.language
                used_fallback = False
        except Exception:
            pass
    record_activity(u.id, "assistant.summarize", "document", doc_id, {"language": language_code})
    return {
        "summary": summary,
        "language": language_code,
        "detected_language": None if used_fallback else language_code,
        "fallback_used": used_fallback,
    }


@router.post("/summarize-file")
async def summarize_uploaded_file(
    file: UploadFile = File(...),
    language: str = Form("en"),
    length: str = Form("medium"),
    u = Depends(current_user),
):
    """Summarize any readable upload (PDF, Word, text, images via OCR...) without saving it first."""
    if language not in LANGUAGE_NAMES:
        raise HTTPException(400, "Choose one of the supported languages")
    if length not in {"short", "medium", "long"}:
        raise HTTPException(400, "Length must be short, medium or long")
    limit = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, "File too large")
    text = await asyncio.to_thread(extract_text, file.filename or "", content)
    language_code, used_fallback = summary_language(text, language)
    budget = {"short": 600, "medium": None, "long": 3500}[length]
    summary = await asyncio.to_thread(summarize, text, budget)
    if not summary.strip():
        raise HTTPException(400, "No readable text was found in the document")

    # If user selected a specific language (e.g. Tamil) and the summary is in another language, translate the summary
    if language != "en":
        try:
            translated = await translate_text(TranslationIn(text=summary, source_language="auto", target_language=language))
            if translated and translated.get("translation"):
                summary = translated["translation"]
                language_code = language
        except Exception:
            pass
    record_activity(u.id, "assistant.summarize", "document", None, {"language": language_code})
    return {
        "summary": summary,
        "language": language_code,
        "words": len(text.split()),
        "summary_words": len(summary.split()),
        "name": Path(file.filename or "document").name,
    }
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5


@router.post("/documents/{doc_id}/chat")
async def chat_with_document(
    doc_id: int,
    x: DocumentChatIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
<<<<<<< HEAD
    text = owned_document_text(doc_id, db, u)
=======
    text = await owned_document_text_async(doc_id, db, u)
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    language = (
        "Tanglish (spoken Tamil in Latin letters mixed with common English words)"
        if x.language == "tanglish"
        else LANGUAGE_NAMES[x.language]
    )
<<<<<<< HEAD
    msgs = [
        {
            "role": "system",
            "content": f"You are Vertex Assistant. Answer the user's questions accurately using the selected document context only. Reply in {language}. Use clean Markdown formatting. If the answer is not in the document, say so instead of guessing.",
        },
        {"role": "system", "content": "Selected document context:\n" + text},
    ]
    msgs.extend({"role": turn.role, "content": turn.content} for turn in x.history)
    msgs.append({"role": "user", "content": x.message})
    return {"reply": await ai_completion(msgs)}
=======
    # Only the passages relevant to this question go to the model: smaller prompt = much faster answers.
    context = await asyncio.to_thread(relevant_context, text, x.message)
    msgs = [
        {
            "role": "system",
            "content": f"You are Vertex Assistant. Answer the user's questions accurately using the selected document context only. CRITICAL: You must write your ENTIRE reply ONLY in {language}. Do not reply in English unless {language} is English. Every sentence, greeting, explanation, and conclusion must strictly be in {language}. Use clean Markdown formatting and keep answers focused. If the answer is not in the document, say so in {language} instead of guessing.",
        },
        {"role": "system", "content": "Selected document context (most relevant passages):\n" + context},
    ]
    msgs.extend({"role": turn.role, "content": turn.content} for turn in x.history[-6:])
    msgs.append({"role": "user", "content": x.message})
    engine = "model"
    try:
        reply = await asyncio.wait_for(ai_completion(msgs), timeout=75)
    except (HTTPException, asyncio.TimeoutError) as error:
        # The chat model is missing / slow: still answer from the document itself instead of failing.
        extract = await asyncio.to_thread(extractive_answer, text, x.message)
        if not extract:
            if isinstance(error, HTTPException):
                raise
            raise HTTPException(504, "The AI model took too long to answer. Please try again.")
        engine = "extractive"
        reply = (
            "_The AI model is not available right now, so here are the most relevant lines from your document:_\n\n"
            + extract
        )
    record_activity(u.id, "assistant.document_chat", "document", doc_id, {"language": x.language})
    return {"reply": reply, "engine": engine}
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5


@router.post("/question-generator")
async def generate_document_questions(
    file: UploadFile = File(...),
    count: int = Form(5),
    language: str = Form("en"),
    u = Depends(current_user),
):
    if not 1 <= count <= 20:
        raise HTTPException(400, "Choose between 1 and 20 questions.")
    if language not in LANGUAGE_NAMES:
        raise HTTPException(400, "Choose a supported question language.")
    content = await file.read(50 * 1024 * 1024 + 1)
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "Files must be 50 MB or smaller")
    text = extract_text(file.filename or "document.pdf", content)
    language_name = (
        "Tanglish (spoken Tamil in Latin letters mixed with English)"
        if language == "tanglish"
        else LANGUAGE_NAMES[language]
    )
    reply = await ai_completion([
        {
            "role": "system",
            "content": f"Create exactly {count} clear study questions from the provided document, in {language_name}. Use only facts in the document. Number each question. Add a concise answer key after the questions, clearly separated.",
        },
        {"role": "user", "content": text},
    ])
<<<<<<< HEAD
=======
    record_activity(u.id, "assistant.question_generation", "assistant", metadata={
        "question_count": count, "language": language,
    })
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return {"questions": reply, "count": count, "language": language}


@router.post("/documents/{doc_id}/translate")
async def translate_document(
    doc_id: int,
    x: DocumentTranslationIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
    text = owned_document_text(doc_id, db, u)
    request = TranslationIn(text=text, source_language=x.source_language, target_language=x.target_language)
<<<<<<< HEAD
    return await translate_text(request)
=======
    result = await translate_text(request)
    record_activity(u.id, "translation.document", "document", doc_id, {
        "source_language": x.source_language, "target_language": x.target_language,
    })
    return result
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5


@router.post("/translate")
async def translate(x: TranslationIn, u = Depends(current_user)):
<<<<<<< HEAD
    return await translate_text(x)
=======
    result = await translate_text(x)
    record_activity(u.id, "translation.text", "translation", metadata={
        "source_language": x.source_language, "target_language": x.target_language,
    })
    return result


HUMANIZE_LLM_TIMEOUT = 45


def _humanize_prompt(x: HumanizeIn) -> str:
    style_guidance = {
        "simple": "Use clear, simple words and straightforward sentences.",
        "professional": "Use polished, professional wording appropriate for work.",
        "conversational": "Use a friendly, natural, conversational tone.",
        "academic": "Use precise, formal academic wording.",
    }
    strength_guidance = (
        "Make only light edits for grammar and flow."
        if x.strength == 1
        else "Rewrite substantially while preserving the original meaning."
        if x.strength == 5
        else f"Use a moderate level of rewriting (strength {x.strength} of 5)."
    )
    return (
        "Rewrite the user's text so it reads like a thoughtful person wrote it: vary sentence length, remove filler and "
        "stiff phrasing, keep the original meaning, facts, names, numbers and language. "
        f"{style_guidance[x.writing_style]} {strength_guidance} "
        "Do not invent details or add commentary. Return only the rewritten text."
    )


async def _humanize_with_llm(x: HumanizeIn) -> str | None:
    """Return the model's rewrite, or None when no model is configured / it fails / the output looks wrong."""
    try:
        raw = await asyncio.wait_for(
            ai_completion([{"role": "system", "content": _humanize_prompt(x)}, {"role": "user", "content": x.text}]),
            timeout=HUMANIZE_LLM_TIMEOUT,
        )
    except (HTTPException, asyncio.TimeoutError):
        return None
    cleaned = clean_model_output(raw or "")
    # Reject empty or truncated answers (a rewrite should be roughly as long as the input).
    if not cleaned or len(cleaned) < 0.35 * len(x.text) or len(cleaned) > 3 * len(x.text) + 200:
        return None
    return cleaned


@router.post("/humanize")
async def humanize(x: HumanizeIn, u = Depends(current_user)):
    notice = ""
    engine = "model"
    rewritten = await _humanize_with_llm(x)
    if rewritten is None:
        engine = "local"
        if looks_non_english(x.text):
            # Round trip through the translation engine: -> English, humanize, -> original language.
            source = detect_document_language(x.text) or "auto"
            try:
                to_english = await translate_text(TranslationIn(text=x.text, source_language=source, target_language="en"))
                english, _ = humanize_local(to_english["translation"], x.writing_style, x.strength)
                back = await translate_text(TranslationIn(text=english, source_language="en", target_language=source if source != "auto" else "en"))
                rewritten = back["translation"]
                engine = "local+translation"
                notice = "Rewritten through the translation engine because no chat model answered."
            except HTTPException:
                raise HTTPException(
                    503,
                    "Humanizing non-English text needs a chat model or a translation engine. "
                    "Add GOOGLE_TRANSLATE_API_KEY or a working LLM_* provider in backend/.env.",
                )
        else:
            rewritten, edits = humanize_local(x.text, x.writing_style, x.strength)
            notice = (
                "Rewritten with the built-in editor (no chat model was available)."
                if edits else "The text already reads naturally, so only light clean-up was needed."
            )
    if not rewritten.strip():
        raise HTTPException(502, "The rewrite came back empty. Please try again.")
    record_activity(u.id, "assistant.humanize", "assistant", metadata={"engine": engine})
    return {"humanized_text": rewritten.strip(), "engine": engine, "notice": notice}
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5


@router.post("/translate-file")
async def translate_file(
    file: UploadFile = File(...),
    source_language: str = Form("auto"),
    target_language: str = Form(...),
    u = Depends(current_user),
):
    if source_language not in SOURCE_LANGUAGES or target_language not in LANGUAGE_NAMES:
        raise HTTPException(400, "Choose one of the supported source and target languages")
    content = await file.read(int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024 + 1)
    if len(content) > int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024:
        raise HTTPException(413, "File too large")
    text = extract_text(file.filename or "", content)
    request = TranslationIn(text=text, source_language=source_language, target_language=target_language)
<<<<<<< HEAD
    return await translate_text(request)
=======
    result = await translate_text(request)
    record_activity(u.id, "translation.file", "translation", metadata={
        "source_language": source_language, "target_language": target_language,
        "file_size_bytes": len(content), "file_extension": Path(file.filename or "").suffix.lstrip("."),
    })
    result["original_text"] = text
    result["detected_source_language"] = detect_document_language(text)
    return result

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
