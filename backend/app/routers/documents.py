<<<<<<< HEAD
import os,uuid
from pathlib import Path
from fastapi import APIRouter,Depends,UploadFile,File,HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Document
from ..security import current_user
router=APIRouter(prefix="/api/documents",tags=["Documents"])
STORE=Path(__file__).resolve().parents[2]/"storage";STORE.mkdir(exist_ok=True)
@router.post("/upload")
async def upload(file:UploadFile=File(...),db:Session=Depends(get_db),u=Depends(current_user)):
    name=Path(file.filename or "file.bin").name; stored=uuid.uuid4().hex+Path(name).suffix.lower(); dest=STORE/stored; size=0
    limit=int(os.getenv("MAX_UPLOAD_MB","50"))*1024*1024
    with dest.open("wb") as f:
        while chunk:=await file.read(1024*1024):
            size+=len(chunk)
            if size>limit: dest.unlink(missing_ok=True);raise HTTPException(413,"File too large")
            f.write(chunk)
    d=Document(owner_id=u.id,original_name=name,stored_name=stored,content_type=file.content_type or "application/octet-stream",size=size)
    db.add(d);db.commit();db.refresh(d)
    return {"id":d.id,"name":name,"size":size,"content_type":d.content_type}
@router.get("")
def listing(db:Session=Depends(get_db),u=Depends(current_user)):
    return [{"id":d.id,"name":d.original_name,"size":d.size} for d in db.query(Document).filter_by(owner_id=u.id).all()]
@router.get("/{doc_id}/download")
def download(doc_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
    d=db.query(Document).filter_by(id=doc_id,owner_id=u.id).first()
    if not d or not (STORE/d.stored_name).exists(): raise HTTPException(404,"Document not found")
    return FileResponse(STORE/d.stored_name,filename=d.original_name,media_type=d.content_type)
@router.delete("/{doc_id}")
def delete(doc_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
    d=db.query(Document).filter_by(id=doc_id,owner_id=u.id).first()
    if not d: raise HTTPException(404,"Document not found")
    (STORE/d.stored_name).unlink(missing_ok=True);db.delete(d);db.commit();return {"success":True}
=======
import os
import uuid
from pathlib import Path
from urllib.parse import quote

import base64

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..activity import record_activity
from ..models import Document, DocumentShare, SignatureRequest, PdfAnnotationSet
from ..security import current_user
from ..storage_service import upload_document, read_document, delete_document

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    name = Path(file.filename or "file.bin").name
    stored = uuid.uuid4().hex + Path(name).suffix.lower()
    content_type = file.content_type or "application/octet-stream"
    limit = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > limit:
            raise HTTPException(413, "File too large")

    try:
        upload_document(stored, bytes(content), content_type)
    except Exception:
        raise HTTPException(502, "Document upload to storage failed")

    try:
        d = Document(
            owner_id=u.id,
            original_name=name,
            stored_name=stored,
            content_type=content_type,
            size=len(content),
        )
        db.add(d)
        db.commit()
        db.refresh(d)
    except Exception:
        db.rollback()
        try:
            delete_document(stored)
        except Exception:
            pass
        raise HTTPException(500, "Document record could not be saved")

    record_activity(
        u.id,
        "document.upload",
        "document",
        d.id,
        {
            "file_size_bytes": len(content),
            "content_type": content_type,
            "file_extension": Path(name).suffix.lstrip("."),
        },
        file_name=name,
    )

    return {
        "id": d.id,
        "name": name,
        "size": len(content),
        "content_type": content_type,
    }


@router.get("")
def listing(db: Session = Depends(get_db), u=Depends(current_user)):
    return [
        {"id": d.id, "name": d.original_name, "size": d.size}
        for d in db.query(Document).filter_by(owner_id=u.id).all()
    ]


@router.get("/{doc_id}/download")
def download(
    doc_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    d = db.query(Document).filter_by(id=doc_id, owner_id=u.id).first()
    if not d:
        raise HTTPException(404, "Document not found")

    try:
        content = read_document(d.stored_name)
    except Exception:
        raise HTTPException(404, "Document file is no longer available")

    filename = quote(d.original_name)
    return Response(
        content=content,
        media_type=d.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        },
    )


@router.delete("/{doc_id}")
def delete(
    doc_id: int,
    db: Session = Depends(get_db),
    u=Depends(current_user),
):
    d = db.query(Document).filter_by(id=doc_id, owner_id=u.id).first()
    if not d:
        raise HTTPException(404, "Document not found")

    try:
        delete_document(d.stored_name)
    except Exception:
        raise HTTPException(502, "Document could not be deleted from storage")

    document_id = d.id
    deleted_name = d.original_name
    db.query(DocumentShare).filter_by(document_id=document_id).delete()
    db.query(SignatureRequest).filter_by(document_id=document_id).delete()
    db.query(PdfAnnotationSet).filter_by(document_id=document_id).delete()
    db.delete(d)
    db.commit()

    record_activity(u.id, "document.delete", "document", document_id, file_name=deleted_name)
    return {"success": True}


def _owned(db: Session, doc_id: int, user_id: int) -> Document:
    d = db.query(Document).filter_by(id=doc_id, owner_id=user_id).first()
    if not d:
        raise HTTPException(404, "Document not found")
    return d


@router.get("/{doc_id}/text")
def document_text(doc_id: int, db: Session = Depends(get_db), u=Depends(current_user)):
    """Readable text of a saved document (PDF, Word, text, spreadsheets, scans via OCR when available)."""
    from .ai import owned_document_text  # local import: ai.py is large and imports this package

    text = owned_document_text(doc_id, db, u)
    limit = 200_000
    return {"text": text[:limit], "truncated": len(text) > limit, "characters": len(text)}


@router.get("/{doc_id}/page/{page}")
def document_page(doc_id: int, page: int, db: Session = Depends(get_db), u=Depends(current_user)):
    """Render one page of a saved PDF as a PNG (base64) for previews and the reader."""
    import pymupdf

    d = _owned(db, doc_id, u.id)
    if not d.original_name.lower().endswith(".pdf"):
        raise HTTPException(400, "Page previews are available for PDF documents only")
    try:
        content = read_document(d.stored_name)
    except Exception:
        raise HTTPException(404, "Document file is no longer available")
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception:
        raise HTTPException(400, "The PDF could not be rendered")
    try:
        if document.needs_pass:
            raise HTTPException(400, "Password-protected PDFs cannot be previewed")
        if page < 1 or page > document.page_count:
            raise HTTPException(400, "Page number is outside this PDF")
        pixmap = document.load_page(page - 1).get_pixmap(matrix=pymupdf.Matrix(1.35, 1.35), alpha=False)
        return {
            "page_number": page,
            "page_count": document.page_count,
            "width": pixmap.width,
            "height": pixmap.height,
            "image_data": base64.b64encode(pixmap.tobytes("png")).decode("ascii"),
        }
    finally:
        document.close()
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
