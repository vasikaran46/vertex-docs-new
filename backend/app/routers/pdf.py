import base64
import binascii
import logging
import io
import os
import posixpath
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ElementTree
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape
from fastapi import APIRouter,Depends,UploadFile,File,HTTPException,Form
from fastapi.responses import StreamingResponse
from pypdf import PdfReader,PdfWriter
from docx import Document as WordDocument
from docx.shared import Inches
from openpyxl import Workbook
from PIL import Image,UnidentifiedImageError
import pymupdf
from pptx import Presentation as PowerPointPresentation
from pptx.util import Inches as PowerPointInches
from reportlab.lib.pagesizes import A4,letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Image as PdfImage,Paragraph,SimpleDocTemplate,Spacer
from ..schemas import EditorExportIn
from ..security import current_user
from ..conversion_service import _image_to_pdf, convert_document
from ..pdf_tool_service import parse_options, process_pdf_tool
router=APIRouter(prefix="/api/pdf",tags=["PDF"])
logger=logging.getLogger(__name__)
def reader(data):
    try:return PdfReader(io.BytesIO(data))
    except Exception as e:raise HTTPException(400,f"Invalid PDF: {e}")
@router.post("/info")
async def info(file:UploadFile=File(...),u=Depends(current_user)):
    r=reader(await file.read());return {"pages":len(r.pages),"metadata":{str(k):str(v) for k,v in (r.metadata or {}).items()}}
@router.post("/merge")
async def merge(files:list[UploadFile]=File(...),u=Depends(current_user)):
    if len(files)<2:raise HTTPException(400,"Upload at least two PDFs")
    w=PdfWriter()
    for f in files:
        for p in reader(await f.read()).pages:w.add_page(p)
    b=io.BytesIO();w.write(b);b.seek(0)
    return StreamingResponse(b,media_type="application/pdf",headers={"Content-Disposition":'attachment; filename="vertex-merged.pdf"'})
@router.post("/split")
async def split(file:UploadFile=File(...),pages:str=Form(...),u=Depends(current_user)):
    r=reader(await file.read());w=PdfWriter()
    try:
        for item in pages.split(","):
            i=int(item.strip())-1
            if i<0 or i>=len(r.pages):raise ValueError()
            w.add_page(r.pages[i])
    except ValueError:raise HTTPException(400,"Use valid comma-separated page numbers, starting at 1")
    b=io.BytesIO();w.write(b);b.seek(0)
    return StreamingResponse(b,media_type="application/pdf",headers={"Content-Disposition":'attachment; filename="vertex-pages.pdf"'})
@router.post("/rotate")
async def rotate(file:UploadFile=File(...),degrees:int=Form(90),u=Depends(current_user)):
    if degrees not in (90,180,270):raise HTTPException(400,"Degrees must be 90, 180 or 270")
    r=reader(await file.read());w=PdfWriter()
    for p in r.pages:p.rotate(degrees);w.add_page(p)
    b=io.BytesIO();w.write(b);b.seek(0)
    return StreamingResponse(b,media_type="application/pdf",headers={"Content-Disposition":'attachment; filename="vertex-rotated.pdf"'})

def pages_to_writer(data:bytes,pages:str,exclude:bool=False):
    source=reader(data);writer=PdfWriter()
    try:
        selected={int(item.strip())-1 for item in pages.split(",") if item.strip()}
        if not selected or any(index<0 or index>=len(source.pages) for index in selected):
            raise ValueError()
    except ValueError:
        raise HTTPException(400,"Use valid comma-separated page numbers, starting at 1")
    indexes=[i for i in range(len(source.pages)) if (i not in selected if exclude else i in selected)]
    if not indexes:
        raise HTTPException(400,"The operation would produce an empty PDF")
    for index in indexes:
        writer.add_page(source.pages[index])
    return writer

def pdf_response(writer:PdfWriter,filename:str):
    output=io.BytesIO();writer.write(output);output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition":f'attachment; filename="{filename}"'},
    )

@router.post("/remove-pages")
async def remove_pages(file:UploadFile=File(...),pages:str=Form(...),u=Depends(current_user)):
    writer=pages_to_writer(await file.read(),pages,exclude=True)
    return pdf_response(writer,"vertex-pages-removed.pdf")

@router.post("/extract-pages")
async def extract_pages(file:UploadFile=File(...),pages:str=Form(...),u=Depends(current_user)):
    writer=pages_to_writer(await file.read(),pages)
    return pdf_response(writer,"vertex-pages-extracted.pdf")

@router.post("/organize")
async def organize_pdf(
    file: UploadFile = File(...),
    page_order: str = Form(...),
    rotations: str = Form(""),
    u=Depends(current_user),
):
    data = await file.read(50 * 1024 * 1024 + 1)
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(413, "Files must be 50 MB or smaller")
    source = reader(data)
    if source.is_encrypted:
        raise HTTPException(400, "Unlock this PDF before organizing its pages.")
    try:
        order = [int(item.strip()) for item in page_order.split(",") if item.strip()]
        if not order or len(order) != len(set(order)) or any(page < 1 or page > len(source.pages) for page in order):
            raise ValueError()
        rotation_map = {}
        for item in rotations.split(","):
            if not item.strip():
                continue
            page_number, degrees = (int(value.strip()) for value in item.split(":", 1))
            if page_number not in order or page_number in rotation_map or degrees not in (0, 90, 180, 270):
                raise ValueError()
            rotation_map[page_number] = degrees
    except ValueError:
        raise HTTPException(
            400,
            "Use unique page numbers within the PDF and rotations of 0, 90, 180 or 270 degrees.",
        )
    writer = PdfWriter()
    for page_number in order:
        page = source.pages[page_number - 1]
        degrees = rotation_map.get(page_number, 0)
        if degrees:
            page.rotate(degrees)
        writer.add_page(page)
    return pdf_response(writer, "vertex-organized.pdf")

@router.post("/protect")
async def protect(file:UploadFile=File(...),password:str=Form(...),u=Depends(current_user)):
    if len(password)<1 or len(password)>128:
        raise HTTPException(400,"Password must contain 1 to 128 characters")
    writer=PdfWriter(clone_from=io.BytesIO(await file.read()))
    writer.encrypt(password)
    return pdf_response(writer,"vertex-protected.pdf")

@router.post("/unlock")
async def unlock(file:UploadFile=File(...),password:str=Form(...),u=Depends(current_user)):
    source=reader(await file.read())
    if source.is_encrypted:
        try:
            decrypted=source.decrypt(password)
        except Exception:
            decrypted=0
        if not decrypted:
            raise HTTPException(400,"Incorrect PDF password")
    writer=PdfWriter()
    for page in source.pages:
        writer.add_page(page)
    return pdf_response(writer,"vertex-unlocked.pdf")

@router.post("/text")
async def extract_text(file:UploadFile=File(...),u=Depends(current_user)):
    source=reader(await file.read())
    return {"text":"\n\n".join(page.extract_text() or "" for page in source.pages)}

def _optimized_pdf(data: bytes, dpi_threshold: int, dpi_target: int, quality: int) -> bytes:
    document = pymupdf.open(stream=data, filetype="pdf")
    try:
        document.rewrite_images(
            dpi_threshold=dpi_threshold,
            dpi_target=dpi_target,
            quality=quality,
        )
        return document.tobytes(
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True,
        )
    finally:
        document.close()


def _rasterized_pdf(data: bytes, dpi: int, quality: int) -> bytes:
    source = pymupdf.open(stream=data, filetype="pdf")
    output = pymupdf.open()
    try:
        for page in source:
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False)
            image_data = pixmap.tobytes("jpeg", jpg_quality=quality)
            output_page = output.new_page(width=page.rect.width, height=page.rect.height)
            output_page.insert_image(output_page.rect, stream=image_data)
        return output.tobytes(garbage=4, deflate=True)
    finally:
        source.close()
        output.close()


@router.post("/compress")
async def compress(
    file: UploadFile = File(...),
    target_size_bytes: int | None = Form(None),
    rasterize_if_needed: bool = Form(False),
    u=Depends(current_user),
):
    data = await file.read(50 * 1024 * 1024 + 1)
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(413, "Files must be 50 MB or smaller")
    if target_size_bytes is not None and not 1 <= target_size_bytes <= 50 * 1024 * 1024:
        raise HTTPException(400, "The target size must be between 1 byte and 50 MB.")

    try:
        if target_size_bytes is None:
            optimized = _optimized_pdf(data, 200, 144, 75)
            mode = "optimized" if len(optimized) < len(data) else "original"
            output = optimized if mode == "optimized" else data
        else:
            output = data
            mode = "original"
            for dpi_threshold, dpi_target, quality in (
                (240, 180, 82),
                (200, 144, 75),
                (160, 120, 65),
                (120, 96, 55),
                (96, 72, 45),
                (72, 48, 35),
            ):
                candidate = _optimized_pdf(data, dpi_threshold, dpi_target, quality)
                if len(candidate) < len(output):
                    output = candidate
                    mode = "optimized"
                if len(candidate) <= target_size_bytes:
                    if len(candidate) <= len(data):
                        output = candidate
                        mode = "optimized"
                    else:
                        output = data
                        mode = "original"
                    break
            else:
                if len(data) <= target_size_bytes:
                    output = data
                elif rasterize_if_needed:
                    for dpi, quality in ((144, 60), (120, 55), (96, 50), (72, 45), (60, 35), (48, 25), (36, 20)):
                        candidate = _rasterized_pdf(data, dpi, quality)
                        if len(candidate) < len(output):
                            output = candidate
                            mode = "rasterized"
                        if len(candidate) <= target_size_bytes:
                            output = candidate
                            mode = "rasterized"
                            break
                if len(output) > target_size_bytes:
                    hint = " Enable page rasterization to allow stronger, lossy compression." if not rasterize_if_needed else ""
                    raise HTTPException(
                        422,
                        f"Could not meet the {target_size_bytes:,}-byte maximum. "
                        f"The smallest result was {len(output):,} bytes.{hint}",
                    )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(400, "The PDF could not be compressed.") from error

    headers = {
        "Content-Disposition": 'attachment; filename="vertex-compressed.pdf"',
        "X-Compression-Actual-Bytes": str(len(output)),
        "X-Compression-Mode": mode,
    }
    if target_size_bytes is not None:
        headers["X-Compression-Target-Bytes"] = str(target_size_bytes)
    return StreamingResponse(
        io.BytesIO(output),
        media_type="application/pdf",
        headers=headers,
    )

@router.post("/preview")
async def preview_page(file:UploadFile=File(...),page:int=Form(1),u=Depends(current_user)):
    data=await file.read(50*1024*1024+1)
    if len(data)>50*1024*1024:
        raise HTTPException(413,"Files must be 50 MB or smaller")
    try:
        document=pymupdf.open(stream=data,filetype="pdf")
        if page<1 or page>document.page_count:
            raise HTTPException(400,"Page number is outside this PDF")
        pdf_page=document.load_page(page-1)
        pixmap=pdf_page.get_pixmap(matrix=pymupdf.Matrix(1.35,1.35),alpha=False)
        image_data=base64.b64encode(pixmap.tobytes("png")).decode("ascii")
        result={"page_number":page,"page_count":document.page_count,"width":pixmap.width,"height":pixmap.height,"image_data":image_data}
        document.close()
        return result
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(400,"The PDF could not be rendered") from error

@router.post("/annotate")
async def annotate_page(
    file:UploadFile=File(...),
    page:int=Form(...),
    overlay_data:str=Form(...),
    u=Depends(current_user),
):
    if len(overlay_data)>8_000_000:
        raise HTTPException(413,"The page annotations are too large")
    try:
        overlay=base64.b64decode(overlay_data,validate=True)
        with Image.open(io.BytesIO(overlay)) as overlay_image:
            if overlay_image.format!="PNG" or overlay_image.width*overlay_image.height>20_000_000:
                raise ValueError()
            overlay_image.verify()
    except (binascii.Error,ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError) as error:
        raise HTTPException(400,"The page annotations are not a valid PNG image") from error
    data=await file.read(50*1024*1024+1)
    if len(data)>50*1024*1024:
        raise HTTPException(413,"Files must be 50 MB or smaller")
    try:
        document=pymupdf.open(stream=data,filetype="pdf")
        if page<1 or page>document.page_count:
            raise HTTPException(400,"Page number is outside this PDF")
        pdf_page=document.load_page(page-1)
        pdf_page.insert_image(pdf_page.rect,stream=overlay,overlay=True)
        output=document.tobytes(garbage=4,deflate=True)
        document.close()
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(400,"The annotations could not be applied to this PDF") from error
    return StreamingResponse(io.BytesIO(output),media_type="application/pdf",headers={"Content-Disposition":'attachment; filename="vertex-edited.pdf"'})

def editor_image(image_data:str|None):
    if not image_data:
        return None
    try:
        decoded=base64.b64decode(image_data,validate=True)
        if len(decoded)>4*1024*1024:
            raise ValueError()
        image=Image.open(io.BytesIO(decoded))
        if image.format not in {"PNG","JPEG","WEBP"} or image.width*image.height>20_000_000:
            raise ValueError()
        image.thumbnail((2400,2400))
        output=io.BytesIO()
        image.convert("RGBA" if "A" in image.getbands() else "RGB").save(output,format="PNG")
        output.seek(0)
        return output
    except (binascii.Error,ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError) as error:
        raise HTTPException(400,"The image must be a valid PNG, JPEG, or WebP under 4 MB") from error

@router.post("/editor-export")
def export_editor(x:EditorExportIn,u=Depends(current_user)):
    image=editor_image(x.image_data)
    drawing=editor_image(x.drawing_data)
    page_preview=editor_image(x.page_preview_data)
    if x.output_format=="txt":
        if image or drawing:
            raise HTTPException(400,"Plain text cannot include images or marks. Choose PDF or DOCX to keep them.")
        data=x.content.encode("utf-8")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition":'attachment; filename="vertex-document.txt"'},
        )
    if x.output_format=="docx":
        document=WordDocument()
        for line in x.content.splitlines():
            document.add_paragraph(line)
        if image:
            document.add_picture(image,width=Inches(5.5))
        if drawing:
            from docx.enum.text import WD_BREAK
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            document.add_picture(drawing,width=Inches(6.2))
        output=io.BytesIO()
        document.save(output)
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition":'attachment; filename="vertex-document.docx"'},
        )

    page_size=A4 if x.page_size=="A4" else letter
    if page_preview:
        output=io.BytesIO()
        document=pdf_canvas.Canvas(output,pagesize=page_size)
        document.drawImage(ImageReader(page_preview),0,0,width=page_size[0],height=page_size[1],mask="auto")
        document.showPage()
        document.save()
        output.seek(0)
        return StreamingResponse(output,media_type="application/pdf",headers={"Content-Disposition":'attachment; filename="vertex-document.pdf"'})
    margin=18*mm
    output=io.BytesIO()
    document=SimpleDocTemplate(
        output,
        pagesize=page_size,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title="Vertex Docs document",
        author="Vertex Docs",
    )
    styles=getSampleStyleSheet()
    story=[]
    for line in x.content.splitlines():
        story.append(Paragraph(escape(line) or "&nbsp;",styles["BodyText"]))
        story.append(Spacer(1,5))
    if image:
        max_width=page_size[0]-2*margin
        max_height=page_size[1]-2*margin
        with Image.open(image) as source_image:
            width,height=source_image.size
        scale=min(max_width/width,max_height/height)
        image.seek(0)
        story.append(PdfImage(image,width=width*scale,height=height*scale))
    if not story:
        story.append(Paragraph("&nbsp;",styles["BodyText"]))
    try:
        document.build(story)
    except UnicodeEncodeError as error:
        raise HTTPException(
            400,
            "This PDF font cannot render one or more characters. Export as DOCX or TXT to preserve all languages.",
        ) from error
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition":'attachment; filename="vertex-document.pdf"'},
    )

@router.post("/convert")
async def convert_file(file:UploadFile=File(...),output_format:str=Form(...),u=Depends(current_user)):
    content=await file.read(50*1024*1024+1)
    if len(content)>50*1024*1024:
        raise HTTPException(413,"Files must be 50 MB or smaller")
    output,media_type,filename=convert_document(content,file.filename or "document",output_format)
    return StreamingResponse(
        io.BytesIO(output),
        media_type=media_type,
        headers={"Content-Disposition":f'attachment; filename="{filename}"'},
    )

@router.post("/scan")
async def scan_to_pdf(
    files: list[UploadFile] = File(...),
    rotations: str = Form(""),
    u=Depends(current_user),
):
    if not files or len(files) > 30:
        raise HTTPException(400, "Choose between 1 and 30 scan images.")
    try:
        rotation_values = [int(item.strip()) for item in rotations.split(",")] if rotations else [0] * len(files)
    except ValueError:
        raise HTTPException(400, "Each scan rotation must be 0, 90, 180 or 270 degrees.")
    if len(rotation_values) != len(files) or any(degrees not in (0, 90, 180, 270) for degrees in rotation_values):
        raise HTTPException(400, "Each scan rotation must be 0, 90, 180 or 270 degrees.")

    writer = PdfWriter()
    total_bytes = 0
    for file, degrees in zip(files, rotation_values):
        image_data = await file.read(10 * 1024 * 1024 + 1)
        total_bytes += len(image_data)
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(413, "Each scan image must be 10 MB or smaller.")
        if total_bytes > 50 * 1024 * 1024:
            raise HTTPException(413, "The combined scan images must be 50 MB or smaller.")
        image_pdf = reader(_image_to_pdf(image_data))
        page = image_pdf.pages[0]
        if degrees:
            page.rotate(degrees)
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    if output.tell() > 100 * 1024 * 1024:
        raise HTTPException(413, "The scanned PDF exceeds the 100 MB output limit.")
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="vertex-scanned.pdf"'},
    )

@router.post("/tools/{tool}")
async def apply_pdf_tool(
    tool: str,
    file: UploadFile = File(...),
    files: list[UploadFile] = File(default=[]),
    options: str = Form("{}"),
    u=Depends(current_user),
):
    content = await file.read(50 * 1024 * 1024 + 1)
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "Files must be 50 MB or smaller")
    additional_files = []
    for additional in files:
        data = await additional.read(50 * 1024 * 1024 + 1)
        if len(data) > 50 * 1024 * 1024:
            raise HTTPException(413, "Files must be 50 MB or smaller")
        additional_files.append((additional.filename or "attachment", data))
    result = process_pdf_tool(tool, content, additional_files, parse_options(options))
    if isinstance(result, dict):
        return result
    content, media_type, filename = result
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
