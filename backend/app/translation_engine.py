"""Provider-based translation engine.

Order of preference is controlled by ``TRANSLATION_PROVIDERS`` (comma separated).
Default: ``indictrans,argos,google,google_free,llm`` (local models first, cloud later).

* ``google``      - Google Cloud Translation (Basic / v2) using ``GOOGLE_TRANSLATE_API_KEY``.
                    Best quality / simplest. Has a free monthly quota on Google Cloud.
* ``indictrans``  - Your own AI4Bharat IndicTrans2 server (``INDICTRANS_URL``). See docs/TRANSLATION.md
                    for the tiny JSON contract. Best for Indian languages if you can host a GPU/CPU service.
* ``argos``       - Offline Argos Translate (``pip install argostranslate``). Only pairs whose
                    language packages are installed are used.
* ``google_free`` - Unofficial keyless Google endpoint. Used when listed in ``TRANSLATION_PROVIDERS`` or when
                    ``TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE=true``.
                    Handy for local development; not suitable for production (no SLA, may be rate-limited).
* ``llm``         - The chat model configured with LLM_* (kept as the last resort).

Every provider raises ``ProviderUnavailable`` when it is not configured / does not support the
language pair, so the engine can quietly move on to the next provider.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

DEFAULT_ORDER = "indictrans,argos,google,google_free,llm"
CHUNK_CHARS = 4500
CONCURRENCY = 4

# ISO code used by the app -> code used by Google
GOOGLE_CODES = {
    "en": "en", "ta": "ta", "hi": "hi", "ml": "ml", "te": "te", "kn": "kn", "ja": "ja",
    "de": "de", "sa": "sa", "bn": "bn", "fr": "fr", "es": "es",
}
# ISO code -> FLORES-200 code used by IndicTrans2
FLORES_CODES = {
    "en": "eng_Latn", "ta": "tam_Taml", "hi": "hin_Deva", "ml": "mal_Mlym", "te": "tel_Telu",
    "kn": "kan_Knda", "bn": "ben_Beng", "sa": "san_Deva",
}
# Argos uses plain ISO 639-1 codes
ARGOS_CODES = {"en", "hi", "bn", "ja", "de", "fr", "es", "ta", "te", "ml", "kn"}


class ProviderUnavailable(Exception):
    """Provider is not configured or cannot handle this language pair."""


class ProviderFailed(Exception):
    """Provider is configured but the call failed (network, quota, bad key...)."""


@dataclass
class EngineResult:
    translation: str
    provider: str
    warnings: list[str] = field(default_factory=list)
    detected_source: str | None = None


def setting(name: str, default: str = "") -> str:
    """Read an env var, honouring backend/.env edits without restarts (same behaviour as llm_setting)."""
    if not os.getenv("VERTEX_IGNORE_ENV_FILE"):
        try:
            from pathlib import Path

            from dotenv import dotenv_values

            values = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
            if values.get(name) and str(values[name]).strip():
                return str(values[name]).strip()
        except Exception:  # pragma: no cover - dotenv problems must never break translation
            pass
    return (os.getenv(name) or default).strip()


def provider_order() -> list[str]:
    return [item.strip().lower() for item in setting("TRANSLATION_PROVIDERS", DEFAULT_ORDER).split(",") if item.strip()]


# --------------------------------------------------------------------------- chunking
def split_text(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Split on paragraph / line / sentence / space boundaries so no chunk is larger than ``limit``."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            for separator in ("\n\n", "\n", ". ", "। ", " "):
                cut = text.rfind(separator, start + limit // 2, end)
                if cut != -1:
                    end = cut + len(separator)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
    return chunks


# --------------------------------------------------------------------------- providers
async def _google_cloud(chunks: list[str], source: str, target: str) -> list[str]:
    key = setting("GOOGLE_TRANSLATE_API_KEY")
    if not key:
        raise ProviderUnavailable("GOOGLE_TRANSLATE_API_KEY is not set")
    if target not in GOOGLE_CODES or (source != "auto" and source not in GOOGLE_CODES):
        raise ProviderUnavailable("language not supported by Google")
    payload: dict = {"q": chunks, "target": GOOGLE_CODES[target], "format": "text"}
    if source != "auto":
        payload["source"] = GOOGLE_CODES[source]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post("https://translation.googleapis.com/language/translate/v2", params={"key": key}, json=payload)
    except httpx.RequestError as error:
        raise ProviderFailed(f"Google Cloud Translation could not be reached: {error.__class__.__name__}") from error
    if response.status_code >= 400:
        try:
            message = response.json()["error"]["message"]
        except Exception:
            message = f"HTTP {response.status_code}"
        raise ProviderFailed(f"Google Cloud Translation error: {message}")
    try:
        items = response.json()["data"]["translations"]
        return [_unescape(item["translatedText"]) for item in items]
    except (KeyError, TypeError, ValueError) as error:
        raise ProviderFailed("Google Cloud Translation returned an unexpected response") from error


def _unescape(value: str) -> str:
    import html

    return html.unescape(value)


def google_free_enabled() -> bool:
    """On when the flag is set, or when the operator explicitly listed google_free in TRANSLATION_PROVIDERS."""
    if setting("TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE").lower() in {"1", "true", "yes", "on"}:
        return True
    explicit = [item.strip().lower() for item in setting("TRANSLATION_PROVIDERS").split(",")]
    return "google_free" in explicit


async def _google_free(chunks: list[str], source: str, target: str) -> list[str]:
    if not google_free_enabled():
        raise ProviderUnavailable("unofficial Google endpoint is disabled")
    if target not in GOOGLE_CODES or (source != "auto" and source not in GOOGLE_CODES):
        raise ProviderUnavailable("language not supported")
    results: list[str] = []
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for chunk in chunks:
            # The unofficial endpoint accepts GET with moderately sized text; split further to be safe.
            pieces = split_text(chunk, 1800)
            translated_pieces: list[str] = []
            for piece in pieces:
                try:
                    response = await client.get(
                        "https://translate.googleapis.com/translate_a/single",
                        params={"client": "gtx", "sl": GOOGLE_CODES.get(source, "auto"), "tl": GOOGLE_CODES[target], "dt": "t", "q": piece},
                    )
                except httpx.RequestError as error:
                    raise ProviderFailed(f"Google (free) could not be reached: {error.__class__.__name__}") from error
                if response.status_code >= 400:
                    raise ProviderFailed(f"Google (free) returned HTTP {response.status_code}")
                try:
                    data = response.json()
                    translated_pieces.append("".join(part[0] for part in data[0] if part and part[0]))
                except (ValueError, IndexError, TypeError) as error:
                    raise ProviderFailed("Google (free) returned an unexpected response") from error
            results.append("\n".join(translated_pieces))
    return results


_RESULT_KEYS = ("translations", "translation", "translated_text", "translatedText", "translated", "output", "outputs", "result", "results", "text")


def _extract_translation(payload) -> str:
    """Accept the common response shapes of IndicTrans2 services and return the translated string."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return "\n".join(_extract_translation(item) for item in payload)
    if isinstance(payload, dict):
        for key in _RESULT_KEYS:
            if key in payload and payload[key] not in (None, ""):
                return _extract_translation(payload[key])
        if isinstance(payload.get("data"), (dict, list, str)):
            return _extract_translation(payload["data"])
    raise ValueError("no translation field")


async def _indictrans_call(client: httpx.AsyncClient, url: str, chunk: str, source: str, target: str) -> str:
    # One payload that carries every common field name, so different service layouts accept it.
    body = {
        "text": chunk, "texts": [chunk], "sentences": [chunk],
        "src_lang": FLORES_CODES[source], "tgt_lang": FLORES_CODES[target],
        "source_language": source, "target_language": target, "source": source, "target": target,
    }
    try:
        response = await client.post(url, json=body)
    except httpx.RequestError as error:
        raise ProviderFailed(f"IndicTrans2 service at {url} could not be reached ({error.__class__.__name__}). Is it running?") from error
    if response.status_code >= 400:
        raise ProviderFailed(f"IndicTrans2 service returned HTTP {response.status_code}: {response.text[:160]}")
    try:
        return _extract_translation(response.json())
    except ValueError as error:
        raise ProviderFailed(f"IndicTrans2 service returned an unrecognised response: {response.text[:160]}") from error


async def _indictrans(chunks: list[str], source: str, target: str) -> list[str]:
    url = setting("INDICTRANS_URL")
    if not url:
        raise ProviderUnavailable("INDICTRANS_URL is not set")
    if source == "auto":
        from .routers.ai import detect_document_language  # local import: avoids a circular import

        source = detect_document_language(" ".join(chunks)) or "auto"
    if source == "auto" or source not in FLORES_CODES or target not in FLORES_CODES:
        raise ProviderUnavailable("language pair not supported by IndicTrans2")
    headers = {}
    token = setting("INDICTRANS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    pivot = source != "en" and target != "en"  # IndicTrans2 services ship en->Indic and Indic->en models
    async with httpx.AsyncClient(timeout=float(setting("INDICTRANS_TIMEOUT", "240")), headers=headers) as client:
        semaphore = asyncio.Semaphore(2)

        async def one(chunk: str) -> str:
            async with semaphore:
                if pivot:
                    english = await _indictrans_call(client, url, chunk, source, "en")
                    return await _indictrans_call(client, url, english, "en", target)
                return await _indictrans_call(client, url, chunk, source, target)

        return list(await asyncio.gather(*(one(chunk) for chunk in chunks)))


def _argos_sync(chunks: list[str], source: str, target: str) -> list[str]:
    try:
        from argostranslate import translate as argos_translate  # type: ignore
    except ImportError as error:
        raise ProviderUnavailable("argostranslate is not installed") from error
    if source == "auto" or source not in ARGOS_CODES or target not in ARGOS_CODES:
        raise ProviderUnavailable("language not supported by Argos")
    languages = {language.code: language for language in argos_translate.get_installed_languages()}
    src, dst = languages.get(source), languages.get(target)
    if not src or not dst:
        raise ProviderUnavailable("Argos language package not installed")
    translation = src.get_translation(dst)
    if translation is None:
        raise ProviderUnavailable("no Argos package for this pair")
    return [translation.translate(chunk) for chunk in chunks]


async def _argos(chunks: list[str], source: str, target: str) -> list[str]:
    return await asyncio.to_thread(_argos_sync, chunks, source, target)


PROVIDERS: dict[str, Callable[[list[str], str, str], Awaitable[list[str]]]] = {
    "google": _google_cloud,
    "indictrans": _indictrans,
    "argos": _argos,
    "google_free": _google_free,
}


def configured_providers() -> list[str]:
    """Names of non-LLM providers that look usable right now (cheap check, no network)."""
    names: list[str] = []
    for name in provider_order():
        if name == "google" and setting("GOOGLE_TRANSLATE_API_KEY"):
            names.append("google")
        elif name == "indictrans" and setting("INDICTRANS_URL"):
            names.append("indictrans")
        elif name == "google_free" and google_free_enabled():
            names.append("google_free")
        elif name == "argos":
            try:
                import argostranslate  # type: ignore  # noqa: F401

                names.append("argos")
            except ImportError:
                pass
    return names


# --------------------------------------------------------------------------- tanglish
_TAMIL_TO_LATIN = {
    "அ": "a", "ஆ": "aa", "இ": "i", "ஈ": "ee", "உ": "u", "ஊ": "oo", "எ": "e", "ஏ": "ae", "ஐ": "ai",
    "ஒ": "o", "ஓ": "oa", "ஔ": "au", "ஃ": "h",
    "க": "k", "ங": "ng", "ச": "s", "ஞ": "nj", "ட": "t", "ண": "n", "த": "th", "ந": "n", "ப": "p",
    "ம": "m", "ய": "y", "ர": "r", "ல": "l", "வ": "v", "ழ": "zh", "ள": "l", "ற": "r", "ன": "n",
    "ஜ": "j", "ஷ": "sh", "ஸ": "s", "ஹ": "h",
}
_VOWEL_SIGNS = {
    "ா": "aa", "ி": "i", "ீ": "ee", "ு": "u", "ூ": "oo", "ெ": "e", "ே": "ae", "ை": "ai", "ொ": "o", "ோ": "oa", "ௌ": "au",
}
_PULLI = "்"


def tamil_to_latin(text: str) -> str:
    """Readable Latin-letter Tamil ('Tanglish' style) transliteration; non-Tamil characters pass through."""
    out: list[str] = []
    chars = list(text)
    for index, ch in enumerate(chars):
        if ch in _TAMIL_TO_LATIN:
            base = _TAMIL_TO_LATIN[ch]
            nxt = chars[index + 1] if index + 1 < len(chars) else ""
            if ch in "அஆஇஈஉஊஎஏஐஒஓஔஃ":
                out.append(base)
            elif nxt in _VOWEL_SIGNS or nxt == _PULLI:
                out.append(base)  # vowel sign / pulli follows and decides the vowel
            else:
                out.append(base + "a")
        elif ch in _VOWEL_SIGNS:
            out.append(_VOWEL_SIGNS[ch])
        elif ch == _PULLI:
            continue
        else:
            out.append(ch)
    return re.sub(r"\s+\n", "\n", "".join(out))


# --------------------------------------------------------------------------- public API
async def translate_with_providers(text: str, source: str, target: str) -> EngineResult | None:
    """Try every configured non-LLM provider in order.

    Returns ``None`` when no provider could be used (so the caller can fall back to the LLM).
    Raises ``ProviderFailed`` only when providers were configured and *all* of them failed.
    """
    order = [name for name in provider_order() if name in PROVIDERS]
    tanglish = target == "tanglish"
    effective_target = "ta" if tanglish else target
    effective_source = "ta" if source == "tanglish" else source
    if effective_source == effective_target and source != "auto":
        if tanglish and source == "ta":
            return EngineResult(translation=tamil_to_latin(text), provider="transliteration")
        return EngineResult(translation=text, provider="none", warnings=["Source and target language are the same."])
    chunks = split_text(text)
    if not chunks:
        return EngineResult(translation="", provider="none")

    errors: list[str] = []
    semaphore = asyncio.Semaphore(CONCURRENCY)

    for name in order:
        provider = PROVIDERS[name]
        try:
            # Providers take the whole batch (google/indictrans batch natively; others loop).
            async with semaphore:
                translated = await provider(chunks, effective_source, effective_target)
        except ProviderUnavailable:
            continue
        except ProviderFailed as error:
            logger.warning("Translation provider %s failed: %s", name, error)
            errors.append(str(error))
            continue
        if len(translated) != len(chunks) or not any(piece.strip() for piece in translated):
            errors.append(f"{name} returned an empty result")
            continue
        result_text = "\n\n".join(piece.strip() for piece in translated)
        if tanglish:
            result_text = tamil_to_latin(result_text)
        return EngineResult(translation=result_text, provider=name)

    if errors:
        raise ProviderFailed(" | ".join(errors))
    return None


# --------------------------------------------------------------------------- diagnostics
SUPPORTED_PAIRS_NOTE = {
    "indictrans": "en, ta, hi, bn, kn, ml, te, sa. Indic to Indic goes through English; Tanglish = Tamil + transliteration. Not ja, de, fr, es.",
    "argos": "Only pairs whose Argos language packs are installed (Argos has no Tamil/Telugu/Malayalam/Kannada models in its default index).",
    "google": "en, ta, hi, ml, te, kn, ja, de, sa, bn, fr, es. Tanglish via Tamil transliteration.",
    "google_free": "Same languages as google. Unofficial endpoint, may be rate limited.",
    "llm": "Anything the chat model can do; quality depends on the model.",
}


async def probe_providers(sample: str = "Hello, how are you?", target: str = "hi") -> list[dict]:
    """Really call each translation provider once and report whether it works. Never returns secrets."""
    report: list[dict] = []
    for name in provider_order():
        if name not in PROVIDERS:
            if name == "llm":
                report.append({"provider": "llm", "configured": bool(setting("LLM_API_KEY")), "working": None, "detail": "Tested through the chat model check.", "supports": SUPPORTED_PAIRS_NOTE["llm"]})
            continue
        entry = {"provider": name, "configured": False, "working": False, "detail": "", "sample": "", "supports": SUPPORTED_PAIRS_NOTE.get(name, "")}
        try:
            out = await asyncio.wait_for(PROVIDERS[name]([sample], "en", target), timeout=90)
            entry["configured"] = True
            text = (out[0] if out else "").strip()
            entry["working"] = bool(text) and text.lower() != sample.lower()
            entry["sample"] = text[:80]
            entry["detail"] = "Working." if entry["working"] else "Returned an empty or unchanged result."
        except ProviderUnavailable as error:
            entry["detail"] = f"Not configured / unavailable: {error}"
        except ProviderFailed as error:
            entry["configured"] = True
            entry["detail"] = str(error)
        except asyncio.TimeoutError:
            entry["configured"] = True
            entry["detail"] = "Timed out after 90 seconds."
        report.append(entry)
    return report
