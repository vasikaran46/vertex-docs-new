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
