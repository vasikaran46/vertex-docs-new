from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActivityLog, Document, User
from ..security import current_admin


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(current_admin)],
)


def _activity_item(event: ActivityLog, email: str | None = None) -> dict:
    item = {
        "id": event.id,
        "user_id": event.user_id,
        "action": event.action,
        "entity_type": event.entity_type,
        "created_at": event.created_at.isoformat() if isinstance(event.created_at, datetime) else event.created_at,
    }
    if email is not None:
        item["user_email"] = email
    return item


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    pdf_operations = db.query(func.count(ActivityLog.id)).filter(ActivityLog.action.startswith("pdf")).scalar() or 0
    translations = db.query(func.count(ActivityLog.id)).filter(ActivityLog.action.startswith("translation")).scalar() or 0
    assistant_usage = db.query(func.count(ActivityLog.id)).filter(ActivityLog.action.startswith("assistant")).scalar() or 0
    return {
        "total_users": db.query(func.count(User.id)).scalar() or 0,
        "total_documents": db.query(func.count(Document.id)).scalar() or 0,
        "total_pdf_operations": pdf_operations,
        "total_translations": translations,
        "total_ai_usage": assistant_usage,
        "historical_activity_limited": True,
        "historical_activity_note": "PDF, translation, and AI totals include tracked activity only since activity logging was enabled.",
    }


@router.get("/activity")
def recent_activity(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    base_query = db.query(ActivityLog, User.email).join(User, User.id == ActivityLog.user_id)
    total = base_query.count()
    rows = (
        base_query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [_activity_item(event, email) for event, email in rows],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get("/users")
def list_users(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    total = query.count()
    users = query.order_by(User.id.asc()).offset(offset).limit(limit).all()
    return {
        "items": [{"id": user.id, "email": user.email} for user in users],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get("/users/{user_id}/activity")
def user_activity(
    user_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if db.query(User.id).filter(User.id == user_id).first() is None:
        raise HTTPException(404, "User not found")

    query = db.query(ActivityLog).filter(ActivityLog.user_id == user_id)
    total = query.count()
    events = (
        query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "user_id": user_id,
        "items": [_activity_item(event) for event in events],
        "limit": limit,
        "offset": offset,
        "total": total,
    }
