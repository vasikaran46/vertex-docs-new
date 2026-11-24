"""Best-effort, privacy-filtered activity logging."""

from __future__ import annotations

import logging
import re
from typing import Any

from .database import SessionLocal
from .models import ActivityLog


logger = logging.getLogger(__name__)

_ALLOWED_ACTIONS = {
    "auth.signup", "auth.login",
    "document.upload", "document.delete",
    "pdf.info", "pdf.merge", "pdf.split", "pdf.rotate", "pdf.remove_pages",
    "pdf.extract_pages", "pdf.organize", "pdf.protect", "pdf.unlock",
    "pdf.text_extract", "pdf.compress", "pdf.preview", "pdf.annotate",
    "pdf.editor_export", "pdf.convert", "pdf.scan", "pdf.tool",
    "translation.text", "translation.file", "translation.document",
    "assistant.message", "assistant.conversion", "assistant.summarize", "assistant.humanize",
    "assistant.document_chat", "assistant.question_generation",
    "assistant.document_conversion",
    "document.share", "document.edit", "document.annotate", "signature.requested", "signature.signed",
}
_ENTITY_TYPES = {
    "user", "document", "pdf_operation", "translation",
    "assistant", "assistant_conversation", "chat_attachment", "signature_request",
}
_INTEGER_FIELDS = {
    "file_size_bytes", "input_size_bytes", "output_size_bytes", "target_size_bytes",
    "file_count", "input_file_count", "attachment_count", "tool_count",
    "page_count", "output_page_count", "selected_page_count", "page_number", "rotation_degrees",
    "rotated_page_count", "question_count",
}
_FORMAT_FIELDS = {"output_format"}
_LANGUAGE_FIELDS = {"language", "source_language", "target_language"}
_LANGUAGES = {"auto", "en", "ta", "hi", "ml", "te", "kn", "ja", "de", "sa", "bn", "fr", "es", "tanglish"}
_METADATA_KEYS = (
    _INTEGER_FIELDS
    | _FORMAT_FIELDS
    | _LANGUAGE_FIELDS
    | {"content_type", "file_extension", "compression_mode", "mode", "streamed", "page_size", "tool"}
)
_SAFE_SLUG = re.compile(r"^[a-z0-9_-]{1,40}$")
_SAFE_FORMATS = {"pdf", "docx", "doc", "txt", "rtf", "html", "csv", "xlsx", "pptx", "jpg", "jpeg", "png", "webp"}


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, int | str | bool]:
    if not isinstance(metadata, dict):
        return {}
    safe: dict[str, int | str | bool] = {}
    for key, value in metadata.items():
        if key not in _METADATA_KEYS:
            continue
        if key in _INTEGER_FIELDS:
            if type(value) is int and 0 <= value <= 2**63 - 1:
                safe[key] = value
        elif key == "streamed":
            if type(value) is bool:
                safe[key] = value
        elif key in _FORMAT_FIELDS:
            if isinstance(value, str) and value.lower() in _SAFE_FORMATS:
                safe[key] = value.lower()
        elif key in _LANGUAGE_FIELDS:
            if isinstance(value, str) and value.lower() in _LANGUAGES:
                safe[key] = value.lower()
        elif key == "content_type":
            if isinstance(value, str) and len(value) <= 120 and re.fullmatch(r"[A-Za-z0-9.+_-]+/[A-Za-z0-9.+_-]+", value):
                safe[key] = value.lower()
        elif key == "file_extension":
            if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9]{1,12}", value.lstrip(".")):
                safe[key] = value.lstrip(".").lower()
        elif key == "compression_mode":
            if value in {"original", "optimized", "rasterized"}:
                safe[key] = value
        elif key == "mode":
            if value in {"chat", "stream", "conversion", "tool"}:
                safe[key] = value
        elif key == "page_size":
            if value in {"A4", "Letter"}:
                safe[key] = value
        elif key == "tool":
            if isinstance(value, str) and _SAFE_SLUG.fullmatch(value):
                safe[key] = value
    return safe


def record_activity(
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    file_name: str | None = None,
) -> bool:
    """Persist an allowlisted event without allowing logging errors to break the route.

    The privacy-filtered ActivityLog (used by the admin dashboard) never stores file names.
    The user's own Document History/notifications do, via events.log_event.
    """
    try:
        from .events import log_event
        meta = metadata if isinstance(metadata, dict) else {}
        log_event(
            user_id, action, file_name=file_name, document_id=entity_id if entity_type == "document" else None,
            file_type=meta.get("output_format") or meta.get("file_extension"),
        )
    except Exception:
        pass
    if type(user_id) is not int or user_id <= 0:
        return False
    if action not in _ALLOWED_ACTIONS or entity_type not in _ENTITY_TYPES:
        return False
    if entity_id is not None and (type(entity_id) is not int or entity_id <= 0):
        return False

    session = None
    try:
        session = SessionLocal()
        session.add(ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=_safe_metadata(metadata),
        ))
        session.commit()
        return True
    except Exception as error:
        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass
        logger.warning("Activity logging failed (%s)", type(error).__name__)
        return False
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
