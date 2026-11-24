import io
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..events import log_event
from ..security import current_user
from ..text_export import SUPPORTED_FORMATS, export_text

router = APIRouter(prefix="/api/export", tags=["Export"])


class TextExportIn(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)
    title: str | None = Field(default=None, max_length=160)
    format: str = Field(min_length=2, max_length=8)
    source: str | None = Field(default=None, max_length=40)  # e.g. translation, humanizer, ocr


@router.get("/formats")
def formats(u=Depends(current_user)):
    return {"formats": list(SUPPORTED_FORMATS)}


@router.post("/text")
def export(x: TextExportIn, u=Depends(current_user)):
    data, media_type, filename = export_text(x.text, x.title, x.format)
    log_event(u.id, "text.export", file_name=filename, detail=f"Exported from {x.source}" if x.source else None)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
