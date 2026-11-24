"""Persistent document history and in-app notifications (best-effort, never breaks a route)."""

from __future__ import annotations

import logging
from pathlib import PurePath

from .database import SessionLocal
from .models import HistoryEvent, Notification

logger = logging.getLogger(__name__)

# action -> (history label, category, notification title or None)
ACTION_INFO: dict[str, tuple[str, str, str | None]] = {
    "document.upload": ("Uploaded", "upload", "File uploaded"),
    "document.delete": ("Deleted", "other", None),
    "document.share": ("Shared", "share", "Document shared"),
    "document.share_revoked": ("Share link revoked", "share", None),
    "document.edit": ("Edited and saved", "edit", "Document saved"),
    "document.annotate": ("Annotations saved", "edit", "Annotations saved"),
    "document.annotated_export": ("Annotated PDF exported", "edit", None),
    "signature.requested": ("Signature requested", "signature", "Signature request sent"),
    "signature.signed": ("Signature completed", "signature", "Document signed"),
    "signature.declined": ("Signature declined", "signature", "Signature declined"),
    "signature.cancelled": ("Signature request cancelled", "signature", None),
    "pdf.info": ("PDF information read", "operation", None),
    "pdf.merge": ("PDFs merged", "operation", "Merge completed"),
    "pdf.split": ("PDF split", "operation", "Split completed"),
    "pdf.rotate": ("PDF rotated", "operation", None),
    "pdf.remove_pages": ("Pages removed", "operation", None),
    "pdf.extract_pages": ("Pages extracted", "operation", None),
    "pdf.organize": ("PDF organized", "operation", None),
    "pdf.protect": ("PDF protected", "operation", "PDF protected"),
    "pdf.unlock": ("PDF unlocked", "operation", "PDF unlocked"),
    "pdf.text_extract": ("Text extracted", "operation", None),
    "pdf.compress": ("PDF compressed", "operation", "Compression completed"),
    "pdf.preview": ("PDF previewed", "operation", None),
    "pdf.annotate": ("PDF annotated", "edit", None),
    "pdf.editor_export": ("Editor document exported", "edit", "Document exported"),
    "pdf.convert": ("Converted", "conversion", "Conversion completed"),
    "pdf.scan": ("Scan converted to PDF", "conversion", "Scan to PDF completed"),
    "pdf.tool": ("PDF tool applied", "operation", "PDF tool completed"),
    "translation.text": ("Text translated", "translation", None),
    "translation.file": ("File translated", "translation", "Translation completed"),
    "translation.document": ("Document translated", "translation", "Translation completed"),
    "assistant.conversion": ("Converted with Assistant", "conversion", "Conversion completed"),
    "assistant.document_conversion": ("Converted with Assistant", "conversion", "Conversion completed"),
    "text.export": ("Text exported", "conversion", "Export completed"),
    "assistant.summarize": ("Summarized with AI", "ai", None),
    "assistant.humanize": ("Text humanized", "ai", "Humanizer finished"),
    "assistant.document_chat": ("Asked AI about document", "ai", None),
    "assistant.question_generation": ("Questions generated", "ai", None),
}

SKIP_ACTIONS = {"auth.signup", "auth.login", "auth.supabase_link", "assistant.message", "pdf.preview"}


def file_type_of(name: str | None, fallback: str | None = None) -> str | None:
    if name:
        suffix = PurePath(name).suffix.lstrip(".").lower()
        if suffix:
            return suffix[:24]
    return fallback[:24] if fallback else None


def log_event(
    user_id: int,
    action: str,
    *,
    file_name: str | None = None,
    document_id: int | None = None,
    file_type: str | None = None,
    detail: str | None = None,
    notify: bool | None = None,
    notification_message: str | None = None,
) -> bool:
    """Persist a history event and (when the action warrants it) a notification."""
    if action in SKIP_ACTIONS or not isinstance(user_id, int) or user_id <= 0:
        return False
    label, category, note_title = ACTION_INFO.get(action, (action.replace(".", " ").replace("_", " ").capitalize(), "other", None))
    session = None
    try:
        session = SessionLocal()
        if not file_name and document_id:
            from .models import Document
            found = session.query(Document.original_name).filter_by(id=document_id, owner_id=user_id).first()
            file_name = found[0] if found else None
        session.add(HistoryEvent(
            user_id=user_id,
            document_id=document_id,
            file_name=(file_name or None) and file_name[:255],
            file_type=file_type_of(file_name, file_type),
            action=label,
            category=category,
            detail=detail[:300] if detail else None,
        ))
        want_notification = (note_title is not None) if notify is None else notify
        if want_notification:
            message = notification_message or (f"{label}: {file_name}" if file_name else label)
            session.add(Notification(
                user_id=user_id,
                kind=category,
                title=note_title or label,
                message=message[:400],
                document_id=document_id,
            ))
        session.commit()
        return True
    except Exception as error:  # pragma: no cover - defensive
        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass
        logger.warning("History logging failed (%s)", type(error).__name__)
        return False
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
