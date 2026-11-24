import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import PurePath
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..events import log_event
from ..mailer import public_app_url, send_email, smtp_configured
from ..models import Document, SignatureRequest, User
from ..pdf_marks import AnnotationError, stamp_signature
from ..security import current_user
from ..storage_service import read_document, upload_document

router = APIRouter(prefix="/api/signatures", tags=["Signatures"])


class SignatureRequestIn(BaseModel):
    document_id: int
    signer_name: str = Field(min_length=1, max_length=120)
    signer_email: EmailStr
    message: str | None = Field(default=None, max_length=500)
    expires_days: int | None = Field(default=14, ge=1, le=90)


class SignIn(BaseModel):
    signature_text: str = Field(min_length=2, max_length=160)
    agree: bool


def _out(r: SignatureRequest, document_name: str | None = None) -> dict:
    return {
        "id": r.id,
        "document_id": r.document_id,
        "document_name": document_name,
        "signer_name": r.signer_name,
        "signer_email": r.signer_email,
        "message": r.message,
        "status": _effective_status(r),
        "created_at": r.created_at.isoformat() + "Z",
        "expires_at": r.expires_at.isoformat() + "Z" if r.expires_at else None,
        "completed_at": r.completed_at.isoformat() + "Z" if r.completed_at else None,
        "signed_document_id": r.signed_document_id,
        "emailed": bool(r.emailed),
        "sign_url": f"{public_app_url()}/?sign={r.token}",
    }


def _effective_status(r: SignatureRequest) -> str:
    if r.status == "pending" and r.expires_at and r.expires_at < datetime.utcnow():
        return "expired"
    return r.status


@router.post("")
def create_request(body: SignatureRequestIn, db: Session = Depends(get_db), u=Depends(current_user)):
    doc = db.query(Document).filter_by(id=body.document_id, owner_id=u.id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.original_name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF documents can be sent for signature")
    request = SignatureRequest(
        document_id=doc.id,
        owner_id=u.id,
        signer_name=body.signer_name.strip(),
        signer_email=str(body.signer_email),
        message=(body.message or "").strip() or None,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(days=body.expires_days) if body.expires_days else None,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    request.emailed = send_email(
        request.signer_email,
        f"{u.name} asked you to sign “{doc.original_name}”",
        f"Hello {request.signer_name},\n\n{u.name} has asked you to sign “{doc.original_name}”.\n"
        f"{(request.message + chr(10) + chr(10)) if request.message else ''}"
        f"Review and sign here:\n{public_app_url()}/?sign={request.token}\n",
    )
    db.commit()
    log_event(u.id, "signature.requested", file_name=doc.original_name, document_id=doc.id,
              detail=f"Requested from {request.signer_name}")
    result = _out(request, doc.original_name)
    result["email_status"] = "sent" if request.emailed else ("failed" if smtp_configured() else "not_configured")
    return result


@router.get("")
def list_requests(db: Session = Depends(get_db), u=Depends(current_user)):
    rows = db.query(SignatureRequest).filter_by(owner_id=u.id).order_by(SignatureRequest.id.desc()).all()
    names = {d.id: d.original_name for d in db.query(Document).filter(Document.id.in_([r.document_id for r in rows] or [0]))}
    return {"items": [_out(r, names.get(r.document_id)) for r in rows]}


@router.post("/{request_id}/cancel")
def cancel_request(request_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    request = db.query(SignatureRequest).filter_by(id=request_id, owner_id=u.id).first()
    if not request:
        raise HTTPException(404, "Signature request not found")
    if request.status != "pending":
        raise HTTPException(409, f"A {request.status} request cannot be cancelled")
    request.status = "cancelled"
    request.completed_at = datetime.utcnow()
    db.commit()
    log_event(u.id, "signature.cancelled", document_id=request.document_id)
    return _out(request)


# ---- public (token-based) signer endpoints: no account required ----------

def _open_request(db: Session, token: str) -> SignatureRequest:
    request = db.query(SignatureRequest).filter_by(token=token).first()
    if not request:
        raise HTTPException(404, "This signature link is not valid")
    return request


@router.get("/public/{token}")
def public_details(token: str, db: Session = Depends(get_db)):
    request = _open_request(db, token)
    doc = db.query(Document).filter_by(id=request.document_id).first()
    owner = db.query(User.name).filter_by(id=request.owner_id).first()
    owner_name = owner[0] if owner else None
    return {
        "document_name": doc.original_name if doc else None,
        "signer_name": request.signer_name,
        "requested_by": owner_name,
        "message": request.message,
        "status": _effective_status(request),
    }


@router.get("/public/{token}/document")
def public_document(token: str, db: Session = Depends(get_db)):
    request = _open_request(db, token)
    if _effective_status(request) != "pending":
        raise HTTPException(409, f"This request is {_effective_status(request)}")
    doc = db.query(Document).filter_by(id=request.document_id).first()
    if not doc:
        raise HTTPException(404, "The document is no longer available")
    try:
        content = read_document(doc.stored_name)
    except Exception:
        raise HTTPException(404, "The document is no longer available")
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.original_name)}"})


@router.post("/public/{token}/sign")
def public_sign(token: str, body: SignIn, db: Session = Depends(get_db)):
    request = _open_request(db, token)
    status = _effective_status(request)
    if status != "pending":
        raise HTTPException(409, f"This request is already {status}")
    if not body.agree:
        raise HTTPException(422, "You must confirm that you agree to sign this document")
    doc = db.query(Document).filter_by(id=request.document_id).first()
    if not doc:
        raise HTTPException(404, "The document is no longer available")
    try:
        source = read_document(doc.stored_name)
        signed = stamp_signature(source, request.signer_name, body.signature_text.strip(), request.id)
    except AnnotationError as error:
        raise HTTPException(422, str(error))
    except Exception:
        raise HTTPException(404, "The document is no longer available")
    stored = uuid.uuid4().hex + ".pdf"
    try:
        upload_document(stored, signed, "application/pdf")
    except Exception:
        raise HTTPException(502, "The signed copy could not be stored")
    signed_name = f"{PurePath(doc.original_name).stem}-signed.pdf"
    signed_doc = Document(owner_id=request.owner_id, original_name=signed_name, stored_name=stored,
                          content_type="application/pdf", size=len(signed))
    db.add(signed_doc)
    db.flush()
    request.status = "signed"
    request.completed_at = datetime.utcnow()
    request.signature_text = body.signature_text.strip()
    request.signed_document_id = signed_doc.id
    db.commit()
    log_event(request.owner_id, "signature.signed", file_name=signed_name, document_id=signed_doc.id,
              detail=f"Signed by {request.signer_name}",
              notification_message=f"{request.signer_name} signed “{doc.original_name}”")
    return {"status": "signed", "message": "Thank you — the document has been signed."}


@router.post("/public/{token}/decline")
def public_decline(token: str, db: Session = Depends(get_db)):
    request = _open_request(db, token)
    status = _effective_status(request)
    if status != "pending":
        raise HTTPException(409, f"This request is already {status}")
    request.status = "declined"
    request.completed_at = datetime.utcnow()
    db.commit()
    log_event(request.owner_id, "signature.declined", document_id=request.document_id,
              detail=f"Declined by {request.signer_name}",
              notification_message=f"{request.signer_name} declined to sign")
    return {"status": "declined"}
