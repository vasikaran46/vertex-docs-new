import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..database import get_db, SessionLocal
from ..activity import record_activity
from ..models import AssistantConversation, AssistantMessage
from ..security import current_user
from .attachments import (
    ingest_attachment,
    get_attachment,
    get_attachment_bytes,
    get_conversation_attachments,
    link_attachment_to_conversation,
    build_system_prompt,
    format_chat_prompt,
)
from .tools import (
    CHATBOT_TOOL_SCHEMAS,
    execute_tool_call,
    tool_convert_document,
    detect_fastpath_intent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chatbot"])


async def _empty_lines():
    return
    yield  # pragma: no cover


async def llm_chat(client: httpx.AsyncClient, base: str, key: str, messages: list[dict[str, Any]], tools: list | None = None) -> tuple[dict[str, Any], str]:
    """Call the chat model with fallbacks.

    Tries every model from LLM_MODEL (comma separated; free OpenRouter fallbacks are appended when all are ':free').
    For each model, if the provider rejects the `tools` parameter (many free models do), it retries without tools.
    Returns (response_json, model_used). Raises 502 with the per-model reasons if everything fails.
    """
    from ..routers.ai import llm_models

    problems: list[str] = []
    for model in llm_models():
        for use_tools in ([True, False] if tools else [False]):
            body: dict[str, Any] = {"model": model, "messages": messages}
            if use_tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            try:
                response = await client.post(base + "/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body)
            except httpx.RequestError as error:
                problems.append(f"{model}: could not connect ({error.__class__.__name__})")
                break
            if response.status_code == 200:
                try:
                    data = response.json()
                    data["choices"][0]["message"]
                    return data, model
                except (ValueError, KeyError, IndexError, TypeError):
                    problems.append(f"{model}: unexpected response")
                    break
            problems.append(f"{model}: HTTP {response.status_code} {response.text[:120]}")
            if response.status_code in (401, 403):
                raise HTTPException(502, "The AI provider rejected LLM_API_KEY. Check the key and LLM_BASE_URL in backend/.env.")
            if use_tools and response.status_code in (400, 404, 422):
                continue  # retry the same model without tool calling
            break
    raise HTTPException(502, "No configured AI model answered. " + " | ".join(problems[-3:]))


def _record_conversion_artifacts(user_id: int, artifacts: list[dict[str, Any]]) -> None:
    for artifact in artifacts:
        document_id = artifact.get("document_id")
        if type(document_id) is not int or document_id <= 0:
            continue
        filename = artifact.get("filename")
        output_format = Path(filename).suffix.lstrip(".") if isinstance(filename, str) else None
        record_activity(
            user_id,
            "assistant.document_conversion",
            "document",
            document_id,
            {
                "output_format": output_format,
                "output_size_bytes": artifact.get("size"),
                "mode": "tool",
            },
        )


class ChatMessageIn(BaseModel):
    text: str = Field(default="", max_length=12000)
    attachment_ids: list[str] = Field(default_factory=list)
    language: Literal["en", "ta", "hi", "ml", "te", "kn", "ja", "de", "sa", "bn", "fr", "es", "tanglish"] = "en"
    conversation_id: int | None = None
    action: str | None = None
    target_format: str | None = None
    stream: bool = True


class RenameConversationIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


def _get_owned_conversation(conversation_id: int, db: Session, user_id: int) -> AssistantConversation:
    conv = db.query(AssistantConversation).filter_by(id=conversation_id, owner_id=user_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found.")
    return conv


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), u = Depends(current_user)):
    items = (
        db.query(AssistantConversation)
        .filter_by(owner_id=u.id)
        .order_by(desc(AssistantConversation.updated_at))
        .limit(50)
        .all()
    )
    return [{"id": item.id, "title": item.title, "updated_at": item.updated_at.isoformat()} for item in items]


@router.post("/conversations")
def create_conversation(db: Session = Depends(get_db), u = Depends(current_user)):
    conv = AssistantConversation(owner_id=u.id, title="New chat")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": conv.id, "title": conv.title, "updated_at": conv.updated_at.isoformat()}


@router.get("/conversations/{conversation_id}")
def get_conversation_detail(conversation_id: int, db: Session = Depends(get_db), u = Depends(current_user)):
    conv = _get_owned_conversation(conversation_id, db, u.id)
    messages = (
        db.query(AssistantMessage)
        .filter_by(conversation_id=conv.id)
        .order_by(AssistantMessage.id)
        .all()
    )
    attachments = get_conversation_attachments(conv.id, u.id)

    formatted_msgs = []
    for m in messages:
        artifacts = []
        clean_text = m.content
        card_match = m.content.find("[DOWNLOAD_CARD:")
        if card_match != -1:
            try:
                card_end = m.content.find("]", card_match)
                card_json = m.content[card_match + len("[DOWNLOAD_CARD:") : card_end]
                card_data = json.loads(card_json)
                artifacts.append(card_data)
                clean_text = m.content[:card_match].strip()
            except Exception:
                pass
        formatted_msgs.append({
            "id": m.id,
            "role": m.role,
            "text": clean_text,
            "created_at": m.created_at.isoformat(),
            "artifacts": artifacts,
        })

    return {
        "id": conv.id,
        "title": conv.title,
        "attachments": [
            {
                "id": a["id"],
                "filename": a["filename"],
                "size": a["size"],
                "extension": a["extension"],
                "is_image": a.get("is_image", False),
                "is_scanned": a.get("is_scanned", False),
            }
            for a in attachments
        ],
        "messages": formatted_msgs,
    }


@router.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    payload: RenameConversationIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
    conv = _get_owned_conversation(conversation_id, db, u.id)
    conv.title = payload.title.strip()[:117]
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {"id": conv.id, "title": conv.title}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), u = Depends(current_user)):
    conv = _get_owned_conversation(conversation_id, db, u.id)
    db.query(AssistantMessage).filter_by(conversation_id=conv.id).delete()
    db.delete(conv)
    db.commit()
    return {"success": True}


@router.post("/attachments")
async def upload_attachment(
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


@router.get("/attachments/{attachment_id}")
def get_attachment_info(attachment_id: str, u = Depends(current_user)):
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


@router.post("/convert")
async def convert_attachment_direct(
    attachment_id: str = Form(...),
    target_format: str = Form(...),
    conversation_id: int | None = Form(None),
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
    """
    Dedicated endpoint for the Convert button & dropdown.
    Executes real server-side conversion directly without touching the LLM.
    """
    res = await run_in_threadpool(tool_convert_document, attachment_id, target_format, u.id, db)
    artifact = res["artifact"]

    if conversation_id:
        conv = _get_owned_conversation(conversation_id, db, u.id)
        reply_text = f"Your {target_format.upper()} conversion of **{artifact['filename']}** is ready!\n\n[DOWNLOAD_CARD:{json.dumps(artifact)}]"
        db.add(AssistantMessage(conversation_id=conv.id, role="assistant", content=reply_text))
        conv.updated_at = datetime.utcnow()
        db.commit()

    record_activity(
        u.id,
        "assistant.document_conversion",
        "document",
        artifact.get("document_id") if type(artifact.get("document_id")) is int else None,
        {"output_format": target_format, "output_size_bytes": artifact.get("size"), "mode": "conversion"},
    )

    return {
        "status": "success",
        "file_id": artifact.get("document_id"),
        "filename": artifact.get("filename"),
        "size": artifact.get("size"),
        "download_url": artifact.get("url"),
        "artifact": artifact,
        "message": res["message"],
    }


@router.post("/message")
async def send_chat_message(
    payload: ChatMessageIn,
    db: Session = Depends(get_db),
    u = Depends(current_user),
):
    """
    Primary chatbot message endpoint:
    1. Deterministic fast-path conversion (no LLM risk).
    2. Server-side tool execution loop with OpenRouter.
    3. Document context injection.
    """
    # 1. Ensure conversation exists
    conv = (
        _get_owned_conversation(payload.conversation_id, db, u.id)
        if payload.conversation_id
        else AssistantConversation(owner_id=u.id, title="New chat")
    )
    if not payload.conversation_id:
        db.add(conv)
        db.flush()

    conv_id = conv.id
    conv_title = str(conv.title or "Chat")

    # 2. Link attachments to this conversation
    for att_id in payload.attachment_ids:
        link_attachment_to_conversation(att_id, conv_id, u.id)

    attachments = get_conversation_attachments(conv_id, u.id)

    # 3. Deterministic Fast Path:
    # If action is 'convert' or user text matches conversion intent
    fastpath = detect_fastpath_intent(payload.text)
    is_conversion_action = payload.action == "convert" or (fastpath and fastpath[0] == "convert")

    if is_conversion_action and attachments:
        tgt_fmt = payload.target_format or (fastpath[1] if fastpath else "pdf") or "pdf"
        target_att = attachments[0]
        try:
            res = await run_in_threadpool(tool_convert_document, target_att["id"], tgt_fmt, u.id, db)
            artifact = res["artifact"]
            reply_text = f"I've converted **{target_att['filename']}** to **{tgt_fmt.upper()}** for you!\n\n[DOWNLOAD_CARD:{json.dumps(artifact)}]"

            db.add(AssistantMessage(conversation_id=conv_id, role="user", content=payload.text or f"Convert to {tgt_fmt.upper()}"))
            db.add(AssistantMessage(conversation_id=conv_id, role="assistant", content=reply_text))
            conv.updated_at = datetime.utcnow()
            db.commit()
            record_activity(
                u.id,
                "assistant.conversion",
                "document",
                artifact.get("document_id") if type(artifact.get("document_id")) is int else None,
                {"output_format": tgt_fmt, "output_size_bytes": artifact.get("size"), "mode": "conversion", "attachment_count": 1},
            )

            if payload.stream:
                async def stream_artifact():
                    yield f"data: {json.dumps({'token': reply_text, 'artifacts': [artifact]})}\n\n"
                    yield f"data: {json.dumps({'done': True, 'reply': reply_text, 'artifacts': [artifact], 'conversation_id': conv_id, 'title': conv_title})}\n\n"

                return StreamingResponse(stream_artifact(), media_type="text/event-stream")

            return {
                "text": reply_text,
                "artifacts": [artifact],
                "conversation_id": conv_id,
                "title": conv_title,
            }
        except HTTPException as e:
            err_msg = f"Conversion error: {e.detail}"
            if payload.stream:
                async def stream_err():
                    yield f"data: {json.dumps({'error': err_msg})}\n\n"
                return StreamingResponse(stream_err(), media_type="text/event-stream")
            raise

    # 4. LLM Completion with Server-Side Function Calling
    key = os.getenv("LLM_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Add LLM_API_KEY to backend/.env")
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")  # first choice; llm_chat() applies the full fallback list

    system_instruction = build_system_prompt(payload.language)
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_instruction}]

    # Load history
    previous = (
        db.query(AssistantMessage)
        .filter_by(conversation_id=conv_id)
        .order_by(desc(AssistantMessage.id))
        .limit(10)
        .all()
    )
    if previous:
        msgs.extend({"role": item.role, "content": item.content} for item in reversed(previous))

    # Format user prompt with injected document content
    formatted_user_prompt, attached_names = format_chat_prompt(payload.text, attachments, query=payload.text)
    msgs.append({"role": "user", "content": formatted_user_prompt})

    user_text = payload.text

    # Streaming mode
    if payload.stream:
        async def stream_generator():
            artifacts_collected = []
            reply_accumulator = []
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    # 1. Initial request with tools (falls back across models / without tools)
                    resp_data, model = await llm_chat(client, base, key, msgs, CHATBOT_TOOL_SCHEMAS)
                    choice = resp_data["choices"][0]
                    message = choice["message"]

                    # Check if the model called a tool
                    if message.get("tool_calls"):
                        msgs.append(message)
                        for tool_call in message["tool_calls"]:
                            fn = tool_call["function"]
                            t_name = fn["name"]
                            try:
                                t_args = json.loads(fn.get("arguments", "{}"))
                            except Exception:
                                t_args = {}

                            # Inject attachment_id if missing and single attachment present
                            if "attachment_id" not in t_args and attachments:
                                t_args["attachment_id"] = attachments[0]["id"]

                            with SessionLocal() as tool_db:
                                try:
                                    t_res, t_art = execute_tool_call(t_name, t_args, u.id, tool_db)
                                    if t_art:
                                        artifacts_collected.append(t_art)
                                except HTTPException as te:
                                    t_res = {"error": te.detail}

                            msgs.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": json.dumps(t_res),
                            })

                        # Stream the final answer after tool execution
                        provider_stream_completed = False
                        async with client.stream(
                            "POST",
                            base + "/chat/completions",
                            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                            json={"model": model, "messages": msgs, "stream": True},
                        ) as follow_up_resp:
                            if follow_up_resp.status_code != 200:
                                fallback_data, _ = await llm_chat(client, base, key, msgs)
                                fallback_text = fallback_data["choices"][0]["message"].get("content") or ""
                                reply_accumulator.append(fallback_text)
                                yield f"data: {json.dumps({'token': fallback_text})}\n\n"
                                provider_stream_completed = True
                            async for line in (follow_up_resp.aiter_lines() if follow_up_resp.status_code == 200 else _empty_lines()):
                                if line.startswith("data: "):
                                    raw = line[6:].strip()
                                    if raw == "[DONE]":
                                        provider_stream_completed = True
                                        break
                                    try:
                                        p = json.loads(raw)
                                        delta = p["choices"][0]["delta"].get("content", "")
                                        if delta:
                                            reply_accumulator.append(delta)
                                            yield f"data: {json.dumps({'token': delta})}\n\n"
                                    except Exception:
                                        pass
                        if not provider_stream_completed:
                            yield f"data: {json.dumps({'error': 'Assistant error: AI provider stream ended before completion.'})}\n\n"
                            return
                    else:
                        # Direct content without tool call
                        content = message.get("content") or ""
                        reply_accumulator.append(content)
                        yield f"data: {json.dumps({'token': content})}\n\n"

                final_text = "".join(reply_accumulator)
                with SessionLocal() as save_db:
                    c = save_db.query(AssistantConversation).filter_by(id=conv_id).first()
                    persisted = False
                    if c:
                        if c.title == "New chat":
                            clean_t = user_text.strip().split("\n")[0][:45]
                            c.title = clean_t + ("…" if len(user_text.strip().split("\n")[0]) > 45 else "")
                        c.updated_at = datetime.utcnow()
                        save_db.add(AssistantMessage(conversation_id=conv_id, role="user", content=user_text))
                        save_db.add(AssistantMessage(conversation_id=conv_id, role="assistant", content=final_text))
                        save_db.commit()
                        title_res = c.title
                        persisted = True
                    else:
                        title_res = "Chat"

                if persisted:
                    _record_conversion_artifacts(u.id, artifacts_collected)
                    record_activity(u.id, "assistant.message", "assistant_conversation", conv_id, {
                        "mode": "stream", "language": payload.language,
                        "streamed": True, "attachment_count": len(attachments),
                        "tool_count": len(artifacts_collected),
                    })
                yield f"data: {json.dumps({'done': True, 'reply': final_text, 'artifacts': artifacts_collected, 'conversation_id': conv_id, 'title': title_res})}\n\n"

            except HTTPException as e:
                yield f"data: {json.dumps({'error': e.detail})}\n\n"
            except Exception as e:
                logger.exception("Error in send_chat_message stream")
                yield f"data: {json.dumps({'error': f'Assistant error: {str(e)}'})}\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    # Non-streaming fallback
    async with httpx.AsyncClient(timeout=90) as client:
        resp_data, model = await llm_chat(client, base, key, msgs, CHATBOT_TOOL_SCHEMAS)
        message = resp_data["choices"][0]["message"]
        artifacts = []

        if message.get("tool_calls"):
            msgs.append(message)
            for tool_call in message["tool_calls"]:
                fn = tool_call["function"]
                try:
                    t_args = json.loads(fn.get("arguments", "{}"))
                except Exception:
                    t_args = {}
                if "attachment_id" not in t_args and attachments:
                    t_args["attachment_id"] = attachments[0]["id"]
                try:
                    t_res, t_art = execute_tool_call(fn["name"], t_args, u.id, db)
                except HTTPException as tool_error:
                    t_res, t_art = {"error": tool_error.detail}, None
                if t_art:
                    artifacts.append(t_art)
                msgs.append({"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(t_res)})

            follow_up, _ = await llm_chat(client, base, key, msgs)
            final_text = follow_up["choices"][0]["message"].get("content") or ""
        else:
            final_text = message.get("content") or ""

        db.add(AssistantMessage(conversation_id=conv_id, role="user", content=user_text))
        db.add(AssistantMessage(conversation_id=conv_id, role="assistant", content=final_text))
        db.commit()
        _record_conversion_artifacts(u.id, artifacts)
        record_activity(u.id, "assistant.message", "assistant_conversation", conv_id, {
            "mode": "chat", "language": payload.language,
            "attachment_count": len(attachments), "tool_count": len(artifacts),
        })

        return {
            "text": final_text,
            "artifacts": artifacts,
            "conversation_id": conv_id,
            "title": conv.title,
        }
