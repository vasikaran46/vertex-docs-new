from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notification
from ..security import current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _out(n: Notification) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "title": n.title,
        "message": n.message,
        "document_id": n.document_id,
        "read": bool(n.is_read),
        "created_at": n.created_at.isoformat() + "Z",
    }


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    query = db.query(Notification).filter_by(user_id=u.id)
    unread = query.filter_by(is_read=False).count()
    if unread_only:
        query = query.filter_by(is_read=False)
    items = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).all()
    return {"items": [_out(n) for n in items], "unread_count": unread}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), u=Depends(current_user)):
    updated = db.query(Notification).filter_by(user_id=u.id, is_read=False).update({"is_read": True})
    db.commit()
    return {"updated": updated}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    n = db.query(Notification).filter_by(id=notification_id, user_id=u.id).first()
    if not n:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    db.commit()
    return _out(n)


@router.delete("/{notification_id}")
def delete_notification(notification_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    n = db.query(Notification).filter_by(id=notification_id, user_id=u.id).first()
    if not n:
        raise HTTPException(404, "Notification not found")
    db.delete(n)
    db.commit()
    return {"success": True}


@router.delete("")
def clear_notifications(db: Session = Depends(get_db), u=Depends(current_user)):
    deleted = db.query(Notification).filter_by(user_id=u.id).delete()
    db.commit()
    return {"deleted": deleted}
