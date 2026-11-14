import io
import json
import logging
import os
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .attachments import (
    get_attachment,
    get_attachment_bytes,
    select_relevant_chunks,
)
from .convert import (
    run_chatbot_conversion,
    save_converted_document_for_user,
    SUPPORTED_CONVERSIONS,
)

logger = logging.getLogger(__name__)

# OpenAI-compatible tool definitions for OpenRouter
CHATBOT_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "convert_document",
            "description": "Convert an attached document to a different file format (e.g. DOCX to PDF, PDF to DOCX, TXT to PDF). Returns download details for the converted file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
                        "description": "The unique ID of the attachment to convert.",
                    },
                    "target_format": {
                        "type": "string",
                        "enum": ["pdf", "docx", "txt"],
                        "description": "The desired target format: 'pdf', 'docx', or 'txt'.",
                    },
                },
                "required": ["attachment_id", "target_format"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read and return the extracted plain text content of an attached document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
                        "description": "The unique ID of the attachment to read.",
                    },
                },
                "required": ["attachment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_info",
            "description": "Get metadata and statistics about an attached document (filename, size, character count, type, scanned status).",
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
                        "description": "The unique ID of the attachment.",
                    },
                },
                "required": ["attachment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_document",
            "description": "Summarize an attached document using a specific style: 'concise', 'detailed', or 'bullet_points'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
                        "description": "The unique ID of the attachment to summarize.",
                    },
                    "style": {
                        "type": "string",
                        "enum": ["concise", "detailed", "bullet_points"],
                        "description": "The summary style desired.",
                    },
                },
                "required": ["attachment_id"],
            },
        },
    },
]


def tool_convert_document(
    attachment_id: str,
    target_format: str,
    owner_id: int,
    db: Session,
) -> dict[str, Any]:
    """
    Executes real server-side document conversion.
    Returns structured artifact data with download URL.
    """
    try:
        content, src_filename = get_attachment_bytes(attachment_id, owner_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(404, f"Attachment could not be accessed: {e}") from e

    src_ext = src_filename.rsplit(".", 1)[-1].lower() if "." in src_filename else ""
    tgt = target_format.lower().strip()
    if tgt == "text":
        tgt = "txt"

    pair = (src_ext, tgt)
    if pair not in SUPPORTED_CONVERSIONS and not (src_ext in {"jpg", "jpeg", "png", "webp"} and tgt == "pdf"):
        raise HTTPException(
            415,
            f"Converting from .{src_ext} to {tgt.upper()} is not currently supported (Coming soon).",
        )

    try:
        out_bytes, media_type, out_filename = run_chatbot_conversion(content, src_filename, tgt)
        saved_doc = save_converted_document_for_user(out_bytes, out_filename, media_type, owner_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Conversion engine error")
        raise HTTPException(500, f"Conversion engine failed: {str(e)}") from e

    return {
        "status": "success",
        "artifact": {
            "type": "download",
            "document_id": saved_doc.id,
            "filename": saved_doc.original_name,
            "size": saved_doc.size,
            "content_type": saved_doc.content_type,
            "url": f"/api/documents/{saved_doc.id}/download",
        },
        "message": f"Successfully converted {src_filename} to {tgt.upper()}.",
    }


def tool_read_document(attachment_id: str, owner_id: int) -> dict[str, Any]:
    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")
    return {
        "filename": att.get("filename"),
        "char_count": len(text),
        "is_scanned": att.get("is_scanned", False),
        "content": text[:15000],
    }


def tool_get_document_info(attachment_id: str, owner_id: int) -> dict[str, Any]:
    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")
    words = len(text.split()) if text else 0
    return {
        "id": att["id"],
        "filename": att.get("filename"),
        "size": att.get("size", 0),
        "extension": att.get("extension"),
        "word_count": words,
        "char_count": len(text),
        "is_image": att.get("is_image", False),
        "is_scanned": att.get("is_scanned", False),
    }


def tool_summarize_document(
    attachment_id: str,
    style: str,
    owner_id: int,
) -> dict[str, Any]:
    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")
    if not text.strip():
        if att.get("is_scanned"):
            return {"error": "OCR not available: this document appears to be a scanned image."}
        return {"error": "Document contains no readable text to summarize."}

    summary_context = select_relevant_chunks(text, "overview summary key points", budget=12000)
    return {
        "filename": att.get("filename"),
        "style": style,
        "document_excerpt": summary_context,
    }


def execute_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    owner_id: int,
    db: Session,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    Executes a registered tool. Returns (result_dict, optional_artifact).
    """
    logger.info("Executing chatbot tool '%s' with args %s", tool_name, arguments)
    if tool_name == "convert_document":
        att_id = arguments.get("attachment_id", "")
        tgt = arguments.get("target_format", "pdf")
        res = tool_convert_document(att_id, tgt, owner_id, db)
        return res, res.get("artifact")

    elif tool_name == "read_document":
        att_id = arguments.get("attachment_id", "")
        res = tool_read_document(att_id, owner_id)
        return res, None

    elif tool_name == "get_document_info":
        att_id = arguments.get("attachment_id", "")
        res = tool_get_document_info(att_id, owner_id)
        return res, None

    elif tool_name == "summarize_document":
        att_id = arguments.get("attachment_id", "")
        style = arguments.get("style", "concise")
        res = tool_summarize_document(att_id, style, owner_id)
        return res, None

    raise HTTPException(400, f"Unknown tool: {tool_name}")


def detect_fastpath_intent(message: str) -> tuple[str, str | None] | None:
    """
    Deterministic fast-path detection:
    Returns (action_type, parameter) or None.
    e.g. ('convert', 'pdf'), ('summarize', None), ('key_points', None)
    """
    msg = message.lower().strip()

    # 1. Conversion intents
    conv_match = re.search(
        r"(?:convert|change|transform|export|save)(?:\s+this)?(?:\s+document|\s+file|\s+it)?\s+(?:in)?to\s+(pdf|docx|txt|text|doc)",
        msg,
    )
    if conv_match:
        tgt = conv_match.group(1).lower()
        return ("convert", "txt" if tgt == "text" else ("docx" if tgt == "doc" else tgt))

    if re.search(r"\bconvert\s+(?:to\s+)?(pdf|docx|txt)\b", msg):
        target = re.search(r"\bconvert\s+(?:to\s+)?(pdf|docx|txt)\b", msg).group(1)
        return ("convert", target)

    if re.search(r"\b(?:make|give)(?:\s+me)?\s+(?:this\s+)?(?:a\s+)?(pdf|docx|txt)\b", msg):
        target = re.search(r"\b(?:make|give)(?:\s+me)?\s+(?:this\s+)?(?:a\s+)?(pdf|docx|txt)\b", msg).group(1)
        return ("convert", target)

    # 2. Summarize intents
    if re.search(r"^(?:summarize|summary|summarise)(?:\s+this|\s+the)?(?:\s+document|\s+file)?$", msg):
        return ("summarize", "concise")

    # 3. Key points intents
    if re.search(r"^(?:extract\s+)?key\s+points(?:\s+of\s+this)?(?:\s+document|\s+file)?$", msg):
        return ("key_points", None)

    # 4. Explain simply intents
    if re.search(r"^explain\s+(?:this\s+)?simply$", msg):
        return ("explain_simply", None)

    return None
