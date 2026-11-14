import asyncio
import base64
import binascii
import io
import json
import logging
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import httpx
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


class RenameConversationIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ChatStreamIn(BaseModel):
    message: str = Field(default="", max_length=12000)
    language: Literal["en", "ta", "hi", "ml", "te", "kn", "ja", "de", "sa", "bn", "fr", "es", "tanglish"] = "en"
    conversation_id: int | None = None
    attachment_ids: list[str] = Field(default_factory=list)
    context: str | None = Field(default=None, max_length=20000)


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
    return text


def owned_document_text(doc_id: int, db: Session, u) -> str:
    item = db.query(Document).filter_by(id=doc_id, owner_id=u.id).first()
    if not item:
        raise HTTPException(404, "Document not found")
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

    async def translate_chunk(chunk: str) -> str:
        async with semaphore:
            return await ai_completion([
                {"role": "system", "content": system_message},
                {"role": "user", "content": chunk},
            ])

    translated = await asyncio.gather(*(translate_chunk(chunk) for chunk in chunks))
    translation = "\n\n".join(part.strip() for part in translated)
    return {"translation": translation, "source_language": x.source_language, "target_language": x.target_language}


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
            content=f"Your {target_format.upper()} conversion of “{filename}” is ready!\n\n[DOWNLOAD_CARD:{json.dumps(card)}]"
        ))
        conversation.updated_at = datetime.utcnow()
        db.commit()

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
        conversation.title = clean_title + ("…" if len(x.message.strip().split("\n")[0]) > 45 else "")
    conversation.updated_at = datetime.utcnow()
    db.add(AssistantMessage(conversation_id=conversation.id, role="user", content=x.message))
    db.add(AssistantMessage(conversation_id=conversation.id, role="assistant", content=reply))
    db.commit()
    return {"reply": reply, "conversation_id": conversation.id, "title": conversation.title}


@router.post("/chat/stream")
async def chat_stream(
    x: ChatStreamIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
    key = os.getenv("LLM_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Add LLM_API_KEY to backend/.env")
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

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
            async with httpx.AsyncClient(timeout=90) as client:
                async with client.stream(
                    "POST",
                    base + "/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": msgs, "stream": True},
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        err = f"AI Provider returned {response.status_code}: {body.decode(errors='replace')[:200]}"
                        yield f"data: {json.dumps({'error': err})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            raw_payload = line[6:].strip()
                            if raw_payload == "[DONE]":
                                break
                            try:
                                payload = json.loads(raw_payload)
                                delta = payload["choices"][0]["delta"].get("content", "")
                                if delta:
                                    collected_tokens.append(delta)
                                    yield f"data: {json.dumps({'token': delta})}\n\n"
                            except Exception:
                                pass

            full_reply = "".join(collected_tokens)
            # Persist to database in new session
            from ..database import SessionLocal
            with SessionLocal() as db_session:
                conv = db_session.query(AssistantConversation).filter_by(id=conversation_id).first()
                if conv:
                    if conv.title == "New chat":
                        clean_title = user_message.strip().split("\n")[0][:45]
                        conv.title = clean_title + ("…" if len(user_message.strip().split("\n")[0]) > 45 else "")
                    conv.updated_at = datetime.utcnow()
                    db_session.add(AssistantMessage(conversation_id=conv.id, role="user", content=user_message))
                    db_session.add(AssistantMessage(conversation_id=conv.id, role="assistant", content=full_reply))
                    db_session.commit()
                    conv_title = conv.title
                else:
                    conv_title = "Chat"

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


@router.post("/documents/{doc_id}/chat")
async def chat_with_document(
    doc_id: int,
    x: DocumentChatIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
    text = owned_document_text(doc_id, db, u)
    language = (
        "Tanglish (spoken Tamil in Latin letters mixed with common English words)"
        if x.language == "tanglish"
        else LANGUAGE_NAMES[x.language]
    )
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
    return await translate_text(request)


@router.post("/translate")
async def translate(x: TranslationIn, u = Depends(current_user)):
    return await translate_text(x)


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
    return await translate_text(request)
