import io
from datetime import datetime
from pathlib import PurePath
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..events import log_event
from ..models import Document, PdfAnnotationSet
from ..pdf_marks import AnnotationError, apply_annotations, validate_annotations
from ..security import current_user
from ..storage_service import read_document

router = APIRouter(prefix="/api/documents", tags=["Annotations"])


def _pdf_document(db: Session, doc_id: int, user_id: int) -> Document:
    doc = db.query(Document).filter_by(id=doc_id, owner_id=user_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.original_name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF documents can be annotated")
    return doc


@router.get("/{doc_id}/annotations")
def get_annotations(doc_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    doc = _pdf_document(db, doc_id, u.id)
    row = db.query(PdfAnnotationSet).filter_by(document_id=doc.id, owner_id=u.id).first()
    return {
        "document_id": doc.id,
        "annotations": row.annotations if row else [],
        "updated_at": row.updated_at.isoformat() + "Z" if row else None,
    }


@router.put("/{doc_id}/annotations")
def save_annotations(
    doc_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    doc = _pdf_document(db, doc_id, u.id)
    try:
        clean = validate_annotations(payload.get("annotations"))
    except AnnotationError as error:
        raise HTTPException(422, str(error))
    row = db.query(PdfAnnotationSet).filter_by(document_id=doc.id).first()
    if row:
        row.annotations = clean
        row.updated_at = datetime.utcnow()
    else:
        row = PdfAnnotationSet(document_id=doc.id, owner_id=u.id, annotations=clean)
        db.add(row)
    db.commit()
    log_event(u.id, "document.annotate", file_name=doc.original_name, document_id=doc.id,
              detail=f"{len(clean)} annotation(s) saved")
    return {"document_id": doc.id, "count": len(clean), "updated_at": row.updated_at.isoformat() + "Z"}


@router.get("/{doc_id}/annotated-pdf")
def annotated_pdf(doc_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    doc = _pdf_document(db, doc_id, u.id)
    row = db.query(PdfAnnotationSet).filter_by(document_id=doc.id, owner_id=u.id).first()
    try:
        source = read_document(doc.stored_name)
    except Exception:
        raise HTTPException(404, "Document file is no longer available")
    try:
        output = apply_annotations(source, row.annotations if row else [])
    except AnnotationError as error:
        raise HTTPException(422, str(error))
    stem = PurePath(doc.original_name).stem
    log_event(u.id, "document.annotated_export", file_name=doc.original_name, document_id=doc.id)
    return Response(
        content=output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(stem + '-annotated.pdf')}"},
    )
