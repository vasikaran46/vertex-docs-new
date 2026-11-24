import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..events import log_event
from ..mailer import public_api_url, send_email, smtp_configured
from ..models import Document, DocumentShare
from ..security import current_user
from ..storage_service import read_document

router = APIRouter(tags=["Sharing"])


class ShareIn(BaseModel):
    recipient_email: EmailStr | None = None
    expires_hours: int | None = Field(default=168, ge=1, le=24 * 90)


def _share_out(s: DocumentShare) -> dict:
    return {
        "id": s.id,
        "document_id": s.document_id,
        "recipient_email": s.recipient_email,
        "created_at": s.created_at.isoformat() + "Z",
        "expires_at": s.expires_at.isoformat() + "Z" if s.expires_at else None,
        "revoked": bool(s.revoked),
        "download_count": s.download_count,
        "emailed": bool(s.emailed),
        "download_path": f"/api/shared/{s.token}",
        "download_url": f"{public_api_url()}/api/shared/{s.token}",
    }


def _own_document(db: Session, doc_id: int, user_id: int) -> Document:
    doc = db.query(Document).filter_by(id=doc_id, owner_id=user_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("/api/documents/{doc_id}/share")
def create_share(doc_id: int, body: ShareIn, db: Session = Depends(get_db), u=Depends(current_user)):
    doc = _own_document(db, doc_id, u.id)
    share = DocumentShare(
        document_id=doc.id,
        owner_id=u.id,
        token=secrets.token_urlsafe(32),
        recipient_email=str(body.recipient_email) if body.recipient_email else None,
        expires_at=datetime.utcnow() + timedelta(hours=body.expires_hours) if body.expires_hours else None,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    emailed = False
    if share.recipient_email:
        emailed = send_email(
            share.recipient_email,
            f"{u.name} shared “{doc.original_name}” with you",
            f"{u.name} shared a document with you via Vertex Docs.\n\nDownload it here:\n"
            f"{public_api_url()}/api/shared/{share.token}\n",
        )
        share.emailed = emailed
        db.commit()
    log_event(
        u.id, "document.share", file_name=doc.original_name, document_id=doc.id,
        detail=f"Shared with {share.recipient_email}" if share.recipient_email else "Share link created",
    )
    result = _share_out(share)
    result["email_status"] = (
        "sent" if emailed else ("failed" if share.recipient_email and smtp_configured()
                                else ("not_configured" if share.recipient_email else "not_requested"))
    )
    return result


@router.get("/api/documents/{doc_id}/shares")
def list_shares(doc_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    _own_document(db, doc_id, u.id)
    rows = db.query(DocumentShare).filter_by(document_id=doc_id, owner_id=u.id).order_by(DocumentShare.id.desc()).all()
    return {"items": [_share_out(s) for s in rows]}


@router.delete("/api/shares/{share_id}")
def revoke_share(share_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    share = db.query(DocumentShare).filter_by(id=share_id, owner_id=u.id).first()
    if not share:
        raise HTTPException(404, "Share link not found")
    share.revoked = True
    db.commit()
    log_event(u.id, "document.share_revoked", document_id=share.document_id)
    return {"success": True}


@router.get("/api/shared/{token}")
def download_shared(token: str, db: Session = Depends(get_db)):
    share = db.query(DocumentShare).filter_by(token=token).first()
    if not share or share.revoked:
        raise HTTPException(404, "This share link is not available")
    if share.expires_at and share.expires_at < datetime.utcnow():
        raise HTTPException(410, "This share link has expired")
    doc = db.query(Document).filter_by(id=share.document_id).first()
    if not doc:
        raise HTTPException(404, "This document is no longer available")
    try:
        content = read_document(doc.stored_name)
    except Exception:
        raise HTTPException(404, "This document is no longer available")
    share.download_count += 1
    db.commit()
    return Response(
        content=content,
        media_type=doc.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.original_name)}"},
    )
