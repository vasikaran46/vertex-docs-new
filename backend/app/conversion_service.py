import io
import logging
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

from docx import Document as WordDocument
from fastapi import HTTPException
from openpyxl import Workbook
from PIL import Image, UnidentifiedImageError
import pymupdf
from pptx import Presentation as PowerPointPresentation
from pptx.util import Inches as PowerPointInches
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


logger = logging.getLogger(__name__)
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_ZIP_ENTRIES = 25
MAX_ZIP_UNPACKED_BYTES = 50 * 1024 * 1024
SUPPORTED_SOURCE_EXTENSIONS = {
    "doc", "docx", "ppt", "pptx", "xls", "xlsx", "html", "htm",
    "jpg", "jpeg", "png", "webp", "txt", "md", "rtf", "hwp", "zip",
    "odt", "ods", "odp", "pages", "csv", "epub", "pdf",
}
SUPPORTED_OUTPUT_FORMATS = {"pdf", "pdfa", "jpg", "png", "docx", "pptx", "xlsx", "txt", "md"}


def _libreoffice_executable() -> str:
    configured = os.getenv("LIBREOFFICE_PATH", "").strip()
    if configured and Path(configured).is_file():
        return configured
    discovered = shutil.which("soffice")
    if discovered:
        return discovered
    candidates = [
        Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "LibreOffice" / "program" / "soffice.exe",
        Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "LibreOffice" / "program" / "soffice.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise HTTPException(503, "LibreOffice is required for this conversion but was not found.")


def _libreoffice_convert(data: bytes, source_extension: str, target: str, output_extension: str) -> bytes:
    executable = _libreoffice_executable()
    with tempfile.TemporaryDirectory(prefix="vertex-convert-") as directory:
        root = Path(directory)
        input_directory = root / "input"
        output_directory = root / "output"
        profile_directory = root / "profile"
        input_directory.mkdir()
        output_directory.mkdir()
        source_path = input_directory / f"source.{source_extension}"
        source_path.write_bytes(data)
        command = [
            executable,
            "--headless",
            "--nologo",
            "--nodefault",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={profile_directory.as_uri()}",
            "--convert-to",
            target,
            "--outdir",
            str(output_directory),
            str(source_path),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        except subprocess.TimeoutExpired as error:
            logger.warning("LibreOffice conversion timed out for %s to %s", source_extension, output_extension)
            raise HTTPException(504, "The conversion took too long. Try a smaller document.") from error
        except OSError as error:
            logger.exception("Could not start LibreOffice for a document conversion")
            raise HTTPException(503, "LibreOffice could not be started. Check the conversion engine installation.") from error
        output_path = output_directory / f"source.{output_extension}"
        if result.returncode != 0 or not output_path.is_file():
            logger.warning(
                "LibreOffice failed converting %s to %s (exit %s): %s",
                source_extension,
                output_extension,
                result.returncode,
                (result.stderr or result.stdout).strip()[:500],
            )
            raise HTTPException(
                415,
                f"LibreOffice could not convert this {source_extension.upper()} file to {output_extension.upper()}. "
                "The file may be invalid or the format may not be supported.",
            )
        output = output_path.read_bytes()
        if len(output) > MAX_FILE_BYTES * 2:
            raise HTTPException(413, "The converted output is too large to return.")
        return output


def _image_to_pdf(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"} or source.width * source.height > 20_000_000:
                raise ValueError()
            image = source.copy()
        image.thumbnail((2400, 2400))
        if "A" in image.getbands():
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="PDF", resolution=150)
        return output.getvalue()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise HTTPException(400, "The image could not be converted to PDF.") from error


def _open_pdf(data: bytes) -> pymupdf.Document:
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:
        raise HTTPException(400, "The uploaded file is not a readable PDF.") from error
    if document.is_encrypted:
        document.close()
        raise HTTPException(400, "Password-protected PDFs cannot be converted until they are unlocked.")
    if document.page_count > MAX_PDF_PAGES:
        document.close()
        raise HTTPException(413, f"PDF conversions support up to {MAX_PDF_PAGES} pages at a time.")
    return document


def _pdf_to_images(data: bytes, image_format: str) -> bytes:
    document = _open_pdf(data)
    output = io.BytesIO()
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                if image_format == "png":
                    image_data = pixmap.tobytes("png")
                else:
                    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                    buffer = io.BytesIO()
                    image.save(buffer, format="JPEG", quality=88, optimize=True)
                    image_data = buffer.getvalue()
                archive.writestr(f"page-{index:03d}.{image_format}", image_data)
    finally:
        document.close()
    return output.getvalue()


def _pdf_to_docx(data: bytes) -> bytes:
    document = _open_pdf(data)
    word = WordDocument()
    try:
        for index, page in enumerate(document, start=1):
            if index > 1:
                word.add_page_break()
            text = page.get_text("text").strip()
            if text:
                word.add_heading(f"Page {index}", level=2)
                for paragraph in text.split("\n\n"):
                    if paragraph.strip():
                        word.add_paragraph(paragraph.strip())
    finally:
        document.close()
    output = io.BytesIO()
    word.save(output)
    return output.getvalue()


def _pdf_to_pptx(data: bytes) -> bytes:
    document = _open_pdf(data)
    presentation = PowerPointPresentation()
    first_page = document[0].rect
    slide_width = 10
    slide_height = max(5.625, min(13.333, slide_width * first_page.height / first_page.width))
    presentation.slide_width = PowerPointInches(slide_width)
    presentation.slide_height = PowerPointInches(slide_height)
    blank_layout = presentation.slide_layouts[6]
    try:
        for page in document:
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4), alpha=False)
            image = io.BytesIO(pixmap.tobytes("png"))
            slide = presentation.slides.add_slide(blank_layout)
            slide.shapes.add_picture(
                image,
                0,
                0,
                width=presentation.slide_width,
                height=presentation.slide_height,
            )
    finally:
        document.close()
    output = io.BytesIO()
    presentation.save(output)
    return output.getvalue()


def _pdf_to_xlsx(data: bytes) -> bytes:
    document = _open_pdf(data)
    workbook = Workbook()
    try:
        for index, page in enumerate(document, start=1):
            sheet = workbook.active if index == 1 else workbook.create_sheet()
            sheet.title = f"Page {index}"
            tables = page.find_tables().tables
            if tables:
                for table in tables:
                    for row in table.extract():
                        sheet.append([cell or "" for cell in row])
                    sheet.append([])
            else:
                for line in page.get_text("text").splitlines():
                    if line.strip():
                        sheet.append([line.strip()])
    finally:
        document.close()
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _pdf_text(data: bytes, markdown: bool) -> str:
    document = _open_pdf(data)
    try:
        pages = [page.get_text("text").strip() for page in document]
    finally:
        document.close()
    if markdown:
        return "\n\n".join(f"## Page {index}\n\n{text}" for index, text in enumerate(pages, start=1) if text)
    return "\n\n".join(text for text in pages if text)


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def _epub_to_pdf(data: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next(
                item for item in container.iter()
                if item.tag.rsplit("}", 1)[-1] == "rootfile"
            ).attrib["full-path"]
            package = ElementTree.fromstring(archive.read(rootfile))
            manifest = {
                item.attrib["id"]: item.attrib["href"]
                for item in package.iter()
                if item.tag.rsplit("}", 1)[-1] == "item" and item.attrib.get("id") and item.attrib.get("href")
            }
            spine = [
                item.attrib["idref"]
                for item in package.iter()
                if item.tag.rsplit("}", 1)[-1] == "itemref" and item.attrib.get("idref")
            ]
            documents: list[str] = []
            root_directory = posixpath.dirname(rootfile)
            for item_id in spine:
                href = manifest.get(item_id)
                if not href:
                    continue
                member_path = posixpath.normpath(posixpath.join(root_directory, href.split("#", 1)[0]))
                if member_path not in names:
                    continue
                parser = _HtmlText()
                parser.feed(archive.read(member_path).decode("utf-8", errors="replace"))
                documents.append(" ".join(parser.parts))
    except (zipfile.BadZipFile, KeyError, ValueError, ElementTree.ParseError, StopIteration) as error:
        raise HTTPException(400, "The EPUB package is invalid or missing its reading order.") from error
    text = "\n\n".join(part for part in documents if part.strip())
    if not text:
        raise HTTPException(400, "The EPUB contains no readable text.")
    output = io.BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(line), styles["BodyText"]) for line in text.splitlines() if line.strip()]
    for _ in range(max(0, len(story) - 1)):
        story.insert(1, Spacer(1, 5))
    try:
        pdf.build(story)
    except UnicodeEncodeError as error:
        raise HTTPException(400, "The EPUB text contains characters this PDF font cannot render.") from error
    return output.getvalue()


def _pages_preview(data: bytes) -> bytes | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                if name.lower().endswith("quicklook/preview.pdf"):
                    return archive.read(name)
    except zipfile.BadZipFile:
        return None
    return None


def _convert_to_pdf(data: bytes, extension: str) -> bytes:
    if extension in {"jpg", "jpeg", "png", "webp"}:
        return _image_to_pdf(data)
    if extension == "epub":
        return _epub_to_pdf(data)
    if extension == "zip":
        return _zip_to_pdf(data)
    if extension == "pages":
        preview = _pages_preview(data)
        if preview:
            return preview
    return _libreoffice_convert(data, extension, "pdf", "pdf")


def _zip_to_pdf(data: bytes) -> bytes:
    writer = PdfWriter()
    total_size = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if not members or len(members) > MAX_ZIP_ENTRIES:
                raise HTTPException(400, f"ZIP to PDF supports 1 to {MAX_ZIP_ENTRIES} files.")
            if any(item.file_size > MAX_ZIP_UNPACKED_BYTES for item in members):
                raise HTTPException(413, "A file inside the ZIP is too large to convert.")
            total_size = sum(item.file_size for item in members)
            if total_size > MAX_ZIP_UNPACKED_BYTES:
                raise HTTPException(413, "The expanded ZIP is too large to convert.")
            for member in members:
                extension = Path(member.filename).suffix.lstrip(".").lower()
                if extension not in SUPPORTED_SOURCE_EXTENSIONS - {"zip"}:
                    raise HTTPException(415, f"The ZIP contains an unsupported file type: {extension or 'unknown'}.")
                member_data = archive.read(member)
                pdf_data = member_data if extension == "pdf" else _convert_to_pdf(member_data, extension)
                source_pdf = PdfReader(io.BytesIO(pdf_data))
                if source_pdf.is_encrypted:
                    raise HTTPException(400, "The ZIP contains a password-protected PDF.")
                for page in source_pdf.pages:
                    writer.add_page(page)
    except zipfile.BadZipFile as error:
        raise HTTPException(400, "The uploaded ZIP archive is invalid.") from error
    if not writer.pages:
        raise HTTPException(400, "The ZIP did not contain any convertible documents.")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def convert_document(data: bytes, filename: str, output_format: str) -> tuple[bytes, str, str]:
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_OUTPUT_FORMATS))
        raise HTTPException(400, f"Choose a supported output format: {supported}.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "Files must be 50 MB or smaller.")
    extension = Path(filename).suffix.lstrip(".").lower()
    if extension not in SUPPORTED_SOURCE_EXTENSIONS:
        raise HTTPException(415, f"Conversion from .{extension or 'unknown'} files is not supported.")

    if extension == "pdf":
        if output_format == "pdf":
            raise HTTPException(400, "This file is already a PDF.")
        if output_format == "pdfa":
            converted = _libreoffice_convert(
                data,
                "pdf",
                'pdf:draw_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"1"}}',
                "pdf",
            )
            return converted, "application/pdf", "vertex-pdfa.pdf"
        if output_format in {"jpg", "png"}:
            converted = _pdf_to_images(data, output_format)
            return converted, "application/zip", f"vertex-pages-{output_format}.zip"
        if output_format == "docx":
            return _pdf_to_docx(data), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "vertex-converted.docx"
        if output_format == "pptx":
            return _pdf_to_pptx(data), "application/vnd.openxmlformats-officedocument.presentationml.presentation", "vertex-converted.pptx"
        if output_format == "xlsx":
            return _pdf_to_xlsx(data), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "vertex-converted.xlsx"
        text = _pdf_text(data, markdown=output_format == "md")
        media_type = "text/markdown; charset=utf-8" if output_format == "md" else "text/plain; charset=utf-8"
        return text.encode("utf-8"), media_type, f"vertex-converted.{output_format}"

    if output_format == "pdf":
        return _convert_to_pdf(data, extension), "application/pdf", "vertex-converted.pdf"
    if output_format == "pdfa":
        raise HTTPException(400, "PDF/A conversion requires a PDF source file.")
    if output_format in {"jpg", "png", "pptx", "xlsx"}:
        raise HTTPException(400, f"Converting this source file to {output_format.upper()} is not supported.")

    if output_format in {"txt", "md"}:
        if extension in {"txt", "md"}:
            text = data.decode("utf-8-sig")
        elif extension == "docx":
            try:
                word = WordDocument(io.BytesIO(data))
                text = "\n".join(paragraph.text for paragraph in word.paragraphs)
            except Exception as error:
                raise HTTPException(400, "The Word document could not be read.") from error
        else:
            converted = _libreoffice_convert(data, extension, "txt:Text", "txt")
            text = converted.decode("utf-8-sig", errors="replace")
        if output_format == "md" and extension != "pdf":
            text = "\n".join(f"- {line}" if line.strip() else "" for line in text.splitlines())
        media_type = "text/markdown; charset=utf-8" if output_format == "md" else "text/plain; charset=utf-8"
        return text.encode("utf-8"), media_type, f"vertex-converted.{output_format}"

    if output_format == "docx":
        if extension == "docx":
            raise HTTPException(400, "This file is already a DOCX.")
        if extension in {"txt", "md"}:
            text = data.decode("utf-8-sig")
            word = WordDocument()
            for line in text.splitlines():
                word.add_paragraph(line)
            output = io.BytesIO()
            word.save(output)
            return output.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "vertex-converted.docx"
        converted = _libreoffice_convert(data, extension, "docx", "docx")
        return converted, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "vertex-converted.docx"

    raise HTTPException(415, "This source and output format combination is not supported.")
