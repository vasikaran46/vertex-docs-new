import difflib
import io
import json
import math
import re
import zipfile
from typing import Any

import pymupdf
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfgen import canvas as pdf_canvas


MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PAGES = 300


def _read_pdf(data: bytes) -> PdfReader:
    try:
        source = PdfReader(io.BytesIO(data))
        if source.is_encrypted:
            raise HTTPException(400, "Unlock this PDF before using this tool.")
        if not source.pages or len(source.pages) > MAX_PAGES:
            raise HTTPException(413, f"PDF tools support 1 to {MAX_PAGES} pages at a time.")
        return source
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(400, "The uploaded file is not a readable PDF.") from error


def _write_pdf(writer: PdfWriter) -> bytes:
    output = io.BytesIO()
    writer.write(output)
    if output.tell() > MAX_PDF_BYTES:
        raise HTTPException(413, "The result is larger than the 50 MB output limit.")
    return output.getvalue()


def _pdf_result(data: bytes, filename: str = "vertex-result.pdf") -> tuple[bytes, str, str]:
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, "The result is larger than the 50 MB output limit.")
    return data, "application/pdf", filename


def _text(options: dict[str, Any], key: str, default: str = "") -> str:
    value = options.get(key, default)
    if not isinstance(value, str):
        raise HTTPException(400, f"{key} must be text.")
    value = value.strip()
    if len(value) > 2000:
        raise HTTPException(400, f"{key} is too long.")
    return value


def _number(options: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> float:
    value = options.get(key, default)
    if isinstance(value, bool):
        raise HTTPException(400, f"{key} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise HTTPException(400, f"{key} must be a number.") from error
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise HTTPException(400, f"{key} must be between {minimum:g} and {maximum:g}.")
    return number


def _zip_parts(source: PdfReader, groups: list[tuple[str, list[int]]]) -> tuple[bytes, str, str]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, indexes in groups:
            if not indexes:
                continue
            writer = PdfWriter()
            for index in indexes:
                writer.add_page(source.pages[index])
            archive.writestr(name, _write_pdf(writer))
    if output.tell() > MAX_PDF_BYTES:
        raise HTTPException(413, "The split archive is larger than the 50 MB output limit.")
    return output.getvalue(), "application/zip", "vertex-split-pages.zip"


def _overlay_page(page, text: str, *, location: str, font_size: float = 10, angle: int = 0):
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    buffer = io.BytesIO()
    overlay = pdf_canvas.Canvas(buffer, pagesize=(width, height))
    if location == "watermark":
        overlay.saveState()
        overlay.setFillAlpha(0.23)
        overlay.setFont("Helvetica-Bold", font_size)
        overlay.translate(width / 2, height / 2)
        overlay.rotate(angle)
        overlay.drawCentredString(0, 0, text)
        overlay.restoreState()
    elif location == "header":
        overlay.setFont("Helvetica", font_size)
        overlay.drawString(36, height - 32, text)
    elif location == "footer":
        overlay.setFont("Helvetica", font_size)
        overlay.drawString(36, 24, text)
    else:
        overlay.setFont("Helvetica", font_size)
        overlay.drawRightString(width - 36, 24, text)
    overlay.save()
    buffer.seek(0)
    page.merge_page(PdfReader(buffer).pages[0])


def _deskew_score(image: Image.Image) -> float:
    grayscale = image.convert("L")
    width, height = grayscale.size
    pixels = grayscale.load()
    rows = [0] * height
    for y in range(height):
        rows[y] = sum(pixels[x, y] < 180 for x in range(width))
    average = sum(rows) / max(1, height)
    return sum((count - average) ** 2 for count in rows)


def _raster_pdf(data: bytes, mode: str, options: dict[str, Any]) -> bytes:
    try:
        source = pymupdf.open(stream=data, filetype="pdf")
    except pymupdf.FileDataError as error:
        raise HTTPException(400, "The PDF could not be rendered.") from error
    page_limit = 50 if mode == "deskew" else MAX_PAGES
    if source.page_count > page_limit:
        source.close()
        raise HTTPException(413, f"This tool supports up to {page_limit} pages.")
    dpi = int(_number(options, "dpi", 144, 72, 300))
    scale = dpi / 72
    output = pymupdf.open()
    for source_page in source:
        pixmap = source_page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            colorspace=pymupdf.csGRAY if mode == "grayscale" else pymupdf.csRGB,
            alpha=False,
        )
        if mode == "flip":
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            direction = _text(options, "direction", "horizontal")
            if direction == "horizontal":
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            elif direction == "vertical":
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            else:
                source.close()
                output.close()
                raise HTTPException(400, "Flip direction must be horizontal or vertical.")
            image_data = io.BytesIO()
            image.save(image_data, format="PNG")
            stream = image_data.getvalue()
        elif mode == "deskew":
            image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("L")
            sample = image.copy()
            sample.thumbnail((350, 350))
            best_angle = 0.0
            best_score = _deskew_score(sample)
            for step in range(-10, 11):
                angle = step / 2
                if angle == 0:
                    continue
                candidate = sample.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=255)
                score = _deskew_score(candidate)
                if score > best_score:
                    best_score = score
                    best_angle = angle
            if best_score < _deskew_score(sample) * 1.01:
                best_angle = 0
            if best_angle:
                image = image.rotate(best_angle, resample=Image.Resampling.BICUBIC, fillcolor=255)
            image_data = io.BytesIO()
            image.save(image_data, format="PNG")
            stream = image_data.getvalue()
        else:
            stream = pixmap.tobytes("png")
        page = output.new_page(width=source_page.rect.width, height=source_page.rect.height)
        page.insert_image(page.rect, stream=stream)
    result = output.tobytes(garbage=4, deflate=True)
    source.close()
    output.close()
    if len(result) > MAX_PDF_BYTES:
        raise HTTPException(413, "The rendered PDF is larger than the 50 MB output limit.")
    return result


def process_pdf_tool(
    tool: str,
    data: bytes,
    additional_files: list[tuple[str, bytes]],
    options: dict[str, Any],
) -> tuple[bytes, str, str] | dict[str, Any]:
    if len(data) > MAX_PDF_BYTES or any(len(content) > MAX_PDF_BYTES for _, content in additional_files):
        raise HTTPException(413, "Files must be 50 MB or smaller.")
    if tool == "repair-pdf":
        try:
            document = pymupdf.open(stream=data, filetype="pdf")
            if document.is_encrypted:
                document.close()
                raise HTTPException(400, "Unlock this PDF before repairing it.")
            if not 1 <= document.page_count <= MAX_PAGES:
                document.close()
                raise HTTPException(413, f"PDF tools support 1 to {MAX_PAGES} pages at a time.")
            result = document.tobytes(garbage=4, deflate=True, clean=True)
            document.close()
        except pymupdf.FileDataError as error:
            raise HTTPException(400, "The PDF is too damaged to repair.") from error
        return _pdf_result(result, "vertex-repaired.pdf")

    source = _read_pdf(data)
    page_count = len(source.pages)

    if tool in {"add-page-numbers", "bates-numbering", "add-watermark", "header-and-footer"}:
        writer = PdfWriter()
        font_size = _number(options, "font_size", 10, 6, 48)
        if tool == "add-watermark":
            text = _text(options, "text")
            if not text:
                raise HTTPException(400, "Enter watermark text.")
            angle = int(_number(options, "angle", 45, -90, 90))
            for page in source.pages:
                _overlay_page(page, text, location="watermark", font_size=font_size, angle=angle)
                writer.add_page(page)
        elif tool == "header-and-footer":
            header = _text(options, "header")
            footer = _text(options, "footer")
            if not header and not footer:
                raise HTTPException(400, "Enter header or footer text.")
            for page in source.pages:
                if header:
                    _overlay_page(page, header, location="header", font_size=font_size)
                if footer:
                    _overlay_page(page, footer, location="footer", font_size=font_size)
                writer.add_page(page)
        else:
            prefix = _text(options, "prefix") if tool == "bates-numbering" else ""
            start = int(_number(options, "start", 1, 1, 999999999))
            digits = int(_number(options, "digits", 6, 1, 12)) if tool == "bates-numbering" else 0
            for index, page in enumerate(source.pages):
                label = f"{prefix}{start + index:0{digits}d}" if digits else str(start + index)
                _overlay_page(page, label, location="number")
                writer.add_page(page)
        return _pdf_result(_write_pdf(writer), f"vertex-{tool}.pdf")

    if tool == "crop-pdf":
        margins = options.get("margins", {})
        if not isinstance(margins, dict):
            raise HTTPException(400, "Margins must be an object with top, right, bottom and left percentages.")
        left = _number(margins, "left", 0, 0, 90)
        right = _number(margins, "right", 0, 0, 90)
        top = _number(margins, "top", 0, 0, 90)
        bottom = _number(margins, "bottom", 0, 0, 90)
        if left + right >= 95 or top + bottom >= 95:
            raise HTTPException(400, "Opposing crop margins must total less than 95%.")
        writer = PdfWriter()
        for page in source.pages:
            box = page.cropbox
            width, height = float(box.width), float(box.height)
            page.cropbox.lower_left = (float(box.left) + width * left / 100, float(box.bottom) + height * bottom / 100)
            page.cropbox.upper_right = (float(box.right) - width * right / 100, float(box.top) - height * top / 100)
            writer.add_page(page)
        return _pdf_result(_write_pdf(writer), "vertex-cropped.pdf")

    if tool == "pdf-forms":
        values = options.get("values", {})
        if not isinstance(values, dict) or any(not isinstance(key, str) or not isinstance(value, (str, int, float, bool)) for key, value in values.items()):
            raise HTTPException(400, 'Enter form values as a JSON object, for example {"name":"Alex"}.')
        writer = PdfWriter(clone_from=io.BytesIO(data))
        fields = writer.get_fields() or {}
        if not fields:
            raise HTTPException(400, "This PDF does not contain fillable form fields.")
        if not values:
            return {"fields": {name: {"type": str(field.get("/FT", "")), "value": str(field.get("/V", ""))} for name, field in fields.items()}}
        unknown = set(values) - set(fields)
        if unknown:
            raise HTTPException(400, "Unknown PDF form field(s): " + ", ".join(sorted(unknown)))
        for page in writer.pages:
            writer.update_page_form_field_values(page, {key: str(value) for key, value in values.items()}, auto_regenerate=False)
        return _pdf_result(_write_pdf(writer), "vertex-form-filled.pdf")

    if tool == "sign-pdf":
        page_number = int(_number(options, "page", 1, 1, page_count))
        signature = _text(options, "signature")
        if not signature and not additional_files:
            raise HTTPException(400, "Enter a signature or upload a signature image.")
        document = pymupdf.open(stream=data, filetype="pdf")
        page = document[page_number - 1]
        x = _number(options, "x", 70, 0, 100) / 100 * page.rect.width
        y = _number(options, "y", 85, 0, 100) / 100 * page.rect.height
        if additional_files:
            image_data = additional_files[0][1]
            rect = pymupdf.Rect(x, y, min(page.rect.width, x + 180), min(page.rect.height, y + 60))
            if rect.is_empty:
                document.close()
                raise HTTPException(400, "Choose a signature position inside the page.")
            try:
                page.insert_image(rect, stream=image_data, keep_proportion=True)
            except Exception as error:
                document.close()
                raise HTTPException(400, "The signature file must be a valid PNG, JPEG or WebP image.") from error
        else:
            page.insert_text((x, y), signature, fontname="heit", fontsize=18, color=(0.12, 0.18, 0.34))
        result = document.tobytes(garbage=4, deflate=True)
        document.close()
        return _pdf_result(result, "vertex-signed.pdf")

    if tool == "compare-pdf":
        if len(additional_files) != 1:
            raise HTTPException(400, "Choose two PDF files to compare.")
        other = _read_pdf(additional_files[0][1])
        first_text = [(page.extract_text() or "").splitlines() for page in source.pages]
        second_text = [(page.extract_text() or "").splitlines() for page in other.pages]
        changes = []
        for index in range(max(len(first_text), len(second_text))):
            left = first_text[index] if index < len(first_text) else []
            right = second_text[index] if index < len(second_text) else []
            if left != right:
                delta = list(difflib.unified_diff(left, right, fromfile="first", tofile="second", lineterm=""))
                changes.append({"page": index + 1, "difference": "\n".join(delta[:80])})
        return {
            "first_page_count": len(first_text),
            "second_page_count": len(second_text),
            "changed_pages": len(changes),
            "identical": not changes,
            "changes": changes[:100],
        }

    if tool == "alternate-and-mix-pdf":
        if len(additional_files) != 1:
            raise HTTPException(400, "Choose two PDFs to alternate.")
        other = _read_pdf(additional_files[0][1])
        writer = PdfWriter()
        for index in range(max(page_count, len(other.pages))):
            if index < page_count:
                writer.add_page(source.pages[index])
            if index < len(other.pages):
                writer.add_page(other.pages[index])
        return _pdf_result(_write_pdf(writer), "vertex-alternated.pdf")

    if tool in {"split-by-half", "split-by-size", "split-by-text", "split-by-bookmarks"}:
        if tool == "split-by-half":
            middle = (page_count + 1) // 2
            groups = [("part-01.pdf", list(range(middle))), ("part-02.pdf", list(range(middle, page_count)))]
        elif tool == "split-by-text":
            needle = _text(options, "text").casefold()
            if not needle:
                raise HTTPException(400, "Enter text to split at.")
            starts = [index for index, page in enumerate(source.pages) if needle in (page.extract_text() or "").casefold()]
            if not starts:
                raise HTTPException(400, "The text was not found in this PDF.")
            boundaries = sorted(set([0, *starts]))
            groups = []
            for index, start_page in enumerate(boundaries):
                end_page = boundaries[index + 1] if index + 1 < len(boundaries) else page_count
                groups.append((f"part-{index + 1:02d}.pdf", list(range(start_page, end_page))))
        elif tool == "split-by-bookmarks":
            destinations = []
            for item in source.outline:
                if isinstance(item, list):
                    continue
                page_index = source.get_destination_page_number(item)
                if page_index is not None and 0 <= page_index < page_count:
                    destinations.append((item.title, page_index))
            destinations.sort(key=lambda entry: entry[1])
            unique = []
            for title, index in destinations:
                if not unique or unique[-1][1] != index:
                    unique.append((title, index))
            if not unique:
                raise HTTPException(400, "This PDF has no usable top-level bookmarks.")
            if unique[0][1] != 0:
                unique.insert(0, ("Start", 0))
            groups = []
            for index, (title, start_page) in enumerate(unique):
                end_page = unique[index + 1][1] if index + 1 < len(unique) else page_count
                safe_title = re.sub(r"[^A-Za-z0-9_-]+", "-", title).strip("-") or f"part-{index + 1:02d}"
                groups.append((f"{index + 1:02d}-{safe_title}.pdf", list(range(start_page, end_page))))
        else:
            target = int(_number(options, "max_size_bytes", 5 * 1024 * 1024, 1024, MAX_PDF_BYTES))
            groups = []
            current = []
            for index, page in enumerate(source.pages):
                candidate = PdfWriter()
                for page_index in [*current, index]:
                    candidate.add_page(source.pages[page_index])
                if len(_write_pdf(candidate)) > target:
                    if not current:
                        raise HTTPException(400, f"Page {index + 1} exceeds the selected split size by itself.")
                    groups.append((f"part-{len(groups) + 1:02d}.pdf", current))
                    current = [index]
                    single = PdfWriter()
                    single.add_page(source.pages[index])
                    if len(_write_pdf(single)) > target:
                        raise HTTPException(400, f"Page {index + 1} exceeds the selected split size by itself.")
                else:
                    current.append(index)
            if current:
                groups.append((f"part-{len(groups) + 1:02d}.pdf", current))
        return _zip_parts(source, groups)

    if tool == "flatten-pdf":
        return _pdf_result(_raster_pdf(data, "flatten", options), "vertex-flattened.pdf")

    if tool == "create-bookmarks":
        entries = _text(options, "bookmarks").splitlines()
        if not entries:
            raise HTTPException(400, "Enter bookmark entries as title:page, one per line.")
        writer = PdfWriter()
        for page in source.pages:
            writer.add_page(page)
        for entry in entries:
            try:
                title, page_text = entry.rsplit(":", 1)
                page_number = int(page_text.strip())
                if not title.strip() or not 1 <= page_number <= page_count:
                    raise ValueError()
            except ValueError as error:
                raise HTTPException(400, "Use valid bookmark entries in the form title:page.") from error
            writer.add_outline_item(title.strip(), page_number - 1)
        return _pdf_result(_write_pdf(writer), "vertex-bookmarked.pdf")

    if tool == "edit-metadata":
        metadata = options.get("metadata", {})
        if not isinstance(metadata, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in metadata.items()):
            raise HTTPException(400, "Metadata must be a JSON object of text values.")
        allowed = {"title", "author", "subject", "keywords", "creator"}
        if not metadata or set(metadata) - allowed:
            raise HTTPException(400, "Set one or more of: title, author, subject, keywords, creator.")
        writer = PdfWriter()
        for page in source.pages:
            writer.add_page(page)
        writer.add_metadata({f"/{key.title()}": value for key, value in metadata.items()})
        return _pdf_result(_write_pdf(writer), "vertex-metadata-updated.pdf")

    if tool == "extract-images":
        document = pymupdf.open(stream=data, filetype="pdf")
        output = io.BytesIO()
        image_count = 0
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for page_index, page in enumerate(document):
                for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                    image_data = document.extract_image(image_info[0])
                    extension = image_data.get("ext", "bin")
                    archive.writestr(f"page-{page_index + 1:03d}-image-{image_index:03d}.{extension}", image_data["image"])
                    image_count += 1
        document.close()
        if not image_count:
            raise HTTPException(400, "No embedded images were found in this PDF.")
        if output.tell() > MAX_PDF_BYTES:
            raise HTTPException(413, "The extracted image archive exceeds the 50 MB output limit.")
        return output.getvalue(), "application/zip", "vertex-extracted-images.zip"

    if tool == "flip-pdf":
        direction = _text(options, "direction", "horizontal")
        if direction not in {"horizontal", "vertical"}:
            raise HTTPException(400, "Flip direction must be horizontal or vertical.")
        writer = PdfWriter()
        for page in source.pages:
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            transform = Transformation().scale(sx=-1, sy=1).translate(tx=width) if direction == "horizontal" else Transformation().scale(sx=1, sy=-1).translate(ty=height)
            page.add_transformation(transform)
            writer.add_page(page)
        return _pdf_result(_write_pdf(writer), "vertex-flipped.pdf")

    if tool == "grayscale-pdf":
        return _pdf_result(_raster_pdf(data, "grayscale", options), "vertex-grayscale.pdf")

    if tool == "n-up-pdf":
        per_sheet = int(_number(options, "pages_per_sheet", 4, 2, 9))
        columns = math.ceil(math.sqrt(per_sheet))
        rows = math.ceil(per_sheet / columns)
        try:
            original = pymupdf.open(stream=data, filetype="pdf")
            first = original[0].rect
            width, height = first.width, first.height
            result = pymupdf.open()
            for start in range(0, original.page_count, per_sheet):
                sheet = result.new_page(width=width, height=height)
                for offset in range(per_sheet):
                    page_index = start + offset
                    if page_index >= original.page_count:
                        break
                    row, column = divmod(offset, columns)
                    slot = pymupdf.Rect(column * width / columns, row * height / rows, (column + 1) * width / columns, (row + 1) * height / rows)
                    sheet.show_pdf_page(slot, original, page_index, keep_proportion=True)
            output = result.tobytes(garbage=4, deflate=True)
            original.close()
            result.close()
        except pymupdf.FileDataError as error:
            raise HTTPException(400, "The PDF could not be laid out on sheets.") from error
        return _pdf_result(output, "vertex-n-up.pdf")

    if tool == "rename-pdf":
        filename = _text(options, "filename", "vertex-renamed.pdf")
        filename = re.sub(r"[^A-Za-z0-9_.-]+", "-", filename).strip(".-")
        if not filename:
            raise HTTPException(400, "Enter a valid output filename.")
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        return _pdf_result(data, filename)

    if tool == "resize-pdf":
        paper = _text(options, "paper", "A4")
        sizes = {"A4": (595.28, 841.89), "A3": (841.89, 1190.55), "Letter": (612, 792), "Legal": (612, 1008)}
        if paper not in sizes:
            raise HTTPException(400, "Choose A4, A3, Letter or Legal.")
        width, height = sizes[paper]
        original = pymupdf.open(stream=data, filetype="pdf")
        result = pymupdf.open()
        for index in range(original.page_count):
            page = result.new_page(width=width, height=height)
            page.show_pdf_page(page.rect, original, index, keep_proportion=True)
        output = result.tobytes(garbage=4, deflate=True)
        original.close()
        result.close()
        return _pdf_result(output, "vertex-resized.pdf")

    if tool == "remove-annotations":
        writer = PdfWriter()
        for page in source.pages:
            page.pop("/Annots", None)
            writer.add_page(page)
        return _pdf_result(_write_pdf(writer), "vertex-annotations-removed.pdf")

    if tool == "deskew-pdf":
        return _pdf_result(_raster_pdf(data, "deskew", options), "vertex-deskewed.pdf")

    raise HTTPException(404, "This PDF tool is not implemented.")


def parse_options(raw: str) -> dict[str, Any]:
    if len(raw) > 20000:
        raise HTTPException(413, "Tool options are too large.")
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as error:
        raise HTTPException(400, "Tool options must be valid JSON.") from error
    if not isinstance(value, dict):
        raise HTTPException(400, "Tool options must be a JSON object.")
    return value
