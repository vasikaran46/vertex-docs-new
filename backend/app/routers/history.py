from pathlib import PurePath

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Document, DocumentShare, HistoryEvent, SignatureRequest
from ..security import current_user

router = APIRouter(prefix="/api/history", tags=["History"])


def _iso(value):
    return value.isoformat() + "Z" if value else None


def _event(e: HistoryEvent) -> dict:
    return {
        "id": e.id,
        "document_id": e.document_id,
        "file_name": e.file_name,
        "file_type": e.file_type,
        "action": e.action,
        "category": e.category,
        "detail": e.detail,
        "created_at": _iso(e.created_at),
    }


@router.get("/events")
def events(
    category: str | None = None,
    document_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    query = db.query(HistoryEvent).filter_by(user_id=u.id)
    if category:
        query = query.filter_by(category=category)
    if document_id is not None:
        query = query.filter_by(document_id=document_id)
    total = query.count()
    rows = query.order_by(HistoryEvent.created_at.desc(), HistoryEvent.id.desc()).offset(offset).limit(limit).all()
    return {"items": [_event(e) for e in rows], "total": total, "limit": limit, "offset": offset}


@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    row = db.query(HistoryEvent).filter_by(id=event_id, user_id=u.id).first()
    if not row:
        raise HTTPException(404, "History entry not found")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.get("/documents")
def documents(db: Session = Depends(get_db), u=Depends(current_user)):
    """Every saved document with its real upload time, last operation and share/signature state."""
    docs = db.query(Document).filter_by(owner_id=u.id).order_by(Document.id.desc()).all()
    ids = [d.id for d in docs]
    events_by_doc: dict[int, list[HistoryEvent]] = {}
    if ids:
        for event in (
            db.query(HistoryEvent)
            .filter(HistoryEvent.user_id == u.id, HistoryEvent.document_id.in_(ids))
            .order_by(HistoryEvent.created_at.asc(), HistoryEvent.id.asc())
            .all()
        ):
            events_by_doc.setdefault(event.document_id, []).append(event)
    active_shares: dict[int, int] = {}
    signature_status: dict[int, str] = {}
    if ids:
        for share in db.query(DocumentShare).filter(DocumentShare.document_id.in_(ids), DocumentShare.revoked.is_(False)):
            active_shares[share.document_id] = active_shares.get(share.document_id, 0) + 1
        for request in db.query(SignatureRequest).filter(SignatureRequest.document_id.in_(ids)).order_by(SignatureRequest.id.asc()):
            signature_status[request.document_id] = request.status
    items = []
    for d in docs:
        history = events_by_doc.get(d.id, [])
        uploaded = next((e for e in history if e.action == "Uploaded"), None)
        last = history[-1] if history else None
        items.append({
            "id": d.id,
            "name": d.original_name,
            "size": d.size,
            "content_type": d.content_type,
            "file_type": PurePath(d.original_name).suffix.lstrip(".").lower() or "file",
            "uploaded_at": _iso(uploaded.created_at) if uploaded else None,
            "last_action": last.action if last else None,
            "last_action_at": _iso(last.created_at) if last else None,
            "operation_count": len(history),
            "active_shares": active_shares.get(d.id, 0),
            "signature_status": signature_status.get(d.id),
        })
    return {"items": items}
