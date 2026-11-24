"""OCR support for images and image-only PDF pages.

The engine is the Tesseract command line tool. It is used through
``subprocess`` so the backend does not need an extra Python package.
If Tesseract is not installed the callers get a clear 503 error that
explains how to enable OCR instead of a silent empty summary.
"""

import io
import logging
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import pymupdf
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Tesseract traineddata codes for the languages Vertex advertises.
LANGUAGE_CODES = {
    "en": "eng",
    "ta": "tam",
    "hi": "hin",
    "ml": "mal",
    "te": "tel",
    "kn": "kan",
    "bn": "ben",
    "sa": "san",
    "fr": "fra",
    "de": "deu",
    "es": "spa",
    "ja": "jpn",
}
DEFAULT_LANGUAGES = ("eng", "tam", "hin")
OCR_TIMEOUT_SECONDS = 120
MAX_OCR_PAGES = 30
MIN_PAGE_TEXT_CHARS = 12


def _candidate_executables() -> list[Path]:
    candidates: list[Path] = []
    configured = os.getenv("TESSERACT_PATH", "").strip()
    if configured:
        candidates.append(Path(configured))
    discovered = shutil.which("tesseract")
    if discovered:
        candidates.append(Path(discovered))
    program_files = Path(os.getenv("ProgramFiles", r"C:\Program Files"))
    program_files_x86 = Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    local_app_data = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    candidates.extend(
        [
            program_files / "Tesseract-OCR" / "tesseract.exe",
            program_files_x86 / "Tesseract-OCR" / "tesseract.exe",
            local_app_data / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            Path("/usr/bin/tesseract"),
            Path("/usr/local/bin/tesseract"),
            Path("/opt/homebrew/bin/tesseract"),
        ]
    )
    return candidates


@lru_cache(maxsize=1)
def tesseract_executable() -> str | None:
    for candidate in _candidate_executables():
        if candidate.is_file():
            return str(candidate)
    return None


def tessdata_directory() -> Path | None:
    """Return an extra traineddata folder when one has been provisioned.

    This lets OCR use Tamil/Hindi data stored outside a protected install
    directory, without changing any environment configuration.
    """
    candidates: list[Path] = []
    configured = os.getenv("TESSDATA_PREFIX", "").strip()
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path(__file__).resolve().parent / "assets" / "tessdata")
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        candidates.append(Path(local_app_data) / "VertexOCR" / "tessdata")
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.glob("*.traineddata")):
            return candidate
    return None


@lru_cache(maxsize=1)
def available_languages() -> tuple[str, ...]:
    executable = tesseract_executable()
    if not executable:
        return ()
    command = [executable, "--list-langs"]
    tessdata = tessdata_directory()
    if tessdata:
        command.extend(["--tessdata-dir", str(tessdata)])
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        logger.warning("Could not list Tesseract languages")
        return ()
    languages: list[str] = []
    for line in (result.stdout or "").splitlines():
        value = line.strip()
        if value and not value.lower().startswith("list of available") and " " not in value:
            languages.append(value)
    return tuple(languages)


def ocr_unavailable_reason() -> str:
    if not tesseract_executable():
        return (
            "OCR needs Tesseract, which is not installed. Install it (for example with "
            "'winget install UB-Mannheim.TesseractOCR'), then add the Tamil/Hindi language "
            "data and restart the backend."
        )
    if not available_languages():
        return (
            "OCR is installed but has no language data. Add the Tesseract traineddata files "
            "for the document's language (eng, tam, hin) and restart the backend."
        )
    return "OCR is not available. Install Tesseract with English, Tamil, and Hindi data."


def selected_languages(language_code: str | None = None) -> list[str]:
    installed = set(available_languages())
    if not installed:
        return []
    if language_code and language_code in LANGUAGE_CODES:
        preferred = LANGUAGE_CODES[language_code]
        if preferred in installed:
            return [preferred]
    configured = [
        item.strip()
        for item in os.getenv("OCR_LANGUAGES", "").replace(",", "+").split("+")
        if item.strip()
    ]
    chosen = [code for code in (configured or DEFAULT_LANGUAGES) if code in installed]
    if not chosen and "eng" in installed:
        chosen.append("eng")
    return list(dict.fromkeys(chosen))


def _run_tesseract(executable: str, image_path: Path, languages: list[str]) -> str:
    with tempfile.TemporaryDirectory(prefix="vertex-ocr-") as directory:
        output_base = Path(directory) / "page"
        command = [
            executable,
            str(image_path),
            str(output_base),
            "-l",
            "+".join(languages),
            "--psm",
            "3",
        ]
        tessdata = tessdata_directory()
        if tessdata:
            command.extend(["--tessdata-dir", str(tessdata)])
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=OCR_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise HTTPException(504, "OCR took too long. Try a smaller image or PDF.") from error
        except OSError as error:
            logger.exception("Could not start Tesseract")
            raise HTTPException(503, ocr_unavailable_reason()) from error
        output_path = output_base.with_suffix(".txt")
        if result.returncode != 0 or not output_path.is_file():
            logger.warning("Tesseract failed (exit %s): %s", result.returncode, (result.stderr or "").strip()[:400])
            raise HTTPException(422, "The text in this image could not be read.")
        return output_path.read_text(encoding="utf-8", errors="replace")


def ocr_image(data: bytes, media_type: str | None = None, language_code: str | None = None) -> str:
    executable = tesseract_executable()
    languages = selected_languages(language_code)
    if not executable or not languages:
        raise HTTPException(503, ocr_unavailable_reason())
    suffix = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(media_type or "", ".png")
    with tempfile.TemporaryDirectory(prefix="vertex-ocr-input-") as directory:
        image_path = Path(directory) / f"image{suffix}"
        image_path.write_bytes(data)
        text = _run_tesseract(executable, image_path, languages)
    text = text.strip()
    if not text:
        raise HTTPException(422, "No readable text was found in this image.")
    return text


def pdf_text_with_ocr(data: bytes, language_code: str | None = None) -> str:
    """Return PDF text, OCR-rendering pages that contain too little text."""
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:
        raise HTTPException(400, "The uploaded file is not a readable PDF.") from error
    if document.needs_pass:
        document.close()
        raise HTTPException(400, "Password-protected PDFs cannot be read until they are unlocked.")
    try:
        parts: list[str] = []
        needs_ocr = False
        for index, page in enumerate(document):
            if index >= MAX_OCR_PAGES:
                break
            text = page.get_text("text").strip()
            if len(text) >= MIN_PAGE_TEXT_CHARS:
                parts.append(text)
            else:
                needs_ocr = True
                parts.append("")
        if not needs_ocr:
            return "\n\n".join(part for part in parts if part)
        if not tesseract_executable() or not selected_languages(language_code):
            partial = "\n\n".join(part for part in parts if part)
            if partial.strip():
                return partial
            raise HTTPException(503, ocr_unavailable_reason())
        for index, page in enumerate(document):
            if index >= len(parts):
                break
            if parts[index]:
                continue
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            parts[index] = ocr_image(
                pixmap.tobytes("png"),
                media_type="image/png",
                language_code=language_code,
            )
        return "\n\n".join(part for part in parts if part)
    finally:
        document.close()


def image_text_with_ocr(data: bytes) -> str:
    """OCR an uploaded image while validating it with Pillow first."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 40_000_000:
                raise HTTPException(413, "The image is too large for OCR.")
            image_format = image.format
            image.verify()
    except HTTPException:
        raise
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise HTTPException(400, "Attach a valid PNG, JPEG, or WebP image.") from error
    media_type = {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "WEBP": "image/webp",
    }.get(image_format or "")
    if not media_type:
        raise HTTPException(415, "OCR supports PNG, JPEG, and WebP images.")
    return ocr_image(data, media_type=media_type)
