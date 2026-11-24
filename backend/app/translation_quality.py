"""Prompting and verification helpers for document translation (no HTTP, no provider calls)."""

from __future__ import annotations

SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "ta": ((0x0B80, 0x0BFF),),
    "hi": ((0x0900, 0x097F),),
    "sa": ((0x0900, 0x097F),),
    "bn": ((0x0980, 0x09FF),),
    "te": ((0x0C00, 0x0C7F),),
    "kn": ((0x0C80, 0x0CFF),),
    "ml": ((0x0D00, 0x0D7F),),
    "ja": ((0x3040, 0x30FF), (0x4E00, 0x9FFF)),
}
LATIN_TARGETS = {"en", "fr", "de", "es", "tanglish"}
NON_LATIN_SOURCE_NAMES = {"ta": "Tamil", "hi": "Hindi", "ml": "Malayalam", "te": "Telugu", "kn": "Kannada",
                           "bn": "Bengali", "sa": "Sanskrit", "ja": "Japanese"}
MIXED_LANGUAGE_RULE = (
    "The text may mix several languages (for example Tamil and English in the same document). "
    "Translate EVERY part into the target language, whichever language it is written in, so no sentence is "
    "left in another language. Keep only proper nouns, e-mail addresses, numbers and untranslatable codes as they are. "
    "Preserve the structure: paragraphs, line breaks, lists and headings."
)


def _in_ranges(code_point: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= code_point <= end for start, end in ranges)


def letters(text: str) -> list[str]:
    return [character for character in text if character.isalpha()]


def target_script_ratio(text: str, language: str) -> float | None:
    """Share of letters written in the target language's script (None if the script is Latin)."""
    ranges = SCRIPT_RANGES.get(language)
    if not ranges:
        return None
    chars = letters(text)
    if not chars:
        return 0.0
    return sum(1 for c in chars if _in_ranges(ord(c), ranges)) / len(chars)


def latin_ratio(text: str) -> float:
    chars = letters(text)
    if not chars:
        return 0.0
    return sum(1 for c in chars if c.isascii() or 0x00C0 <= ord(c) <= 0x024F) / len(chars)


def leftover_ratio(text: str, language: str) -> float:
    """Fraction of letters that are NOT in the target language's script/alphabet."""
    ratio = target_script_ratio(text, language)
    if ratio is not None:
        return 1.0 - ratio
    return 1.0 - latin_ratio(text)


def build_system_message(source: str, target: str, language_code: str, *, strict: bool = False) -> str:
    tanglish_rule = (
        " Use natural spoken Tamil expressed in Latin letters, mixed with common English words; do not use Tamil script."
        if language_code == "tanglish" else ""
    )
    strict_rule = (
        " IMPORTANT: your previous answer still contained text in other languages. "
        f"Write the complete answer in {target} only." if strict else ""
    )
    return (
        f"Translate the user's text into {target}. The source language is {source}; if it is auto, identify it for each part. "
        f"{MIXED_LANGUAGE_RULE} Preserve meaning, names and tone. Return only the translation, with no notes.{tanglish_rule}{strict_rule}"
    )


def needs_retry(source_chunk: str, translated_chunk: str, language_code: str) -> bool:
    """True when a script-language translation still contains a lot of non-target text."""
    if language_code == "tanglish" or not letters(source_chunk) or len(letters(translated_chunk)) < 3:
        return False
    if language_code in SCRIPT_RANGES:
        return leftover_ratio(translated_chunk, language_code) > 0.35
    # Latin targets: only flag when a lot of the output is still in another script.
    return target_script_ratio(translated_chunk, "ta") is not None and any(
        (target_script_ratio(translated_chunk, code) or 0) > 0.3 for code in SCRIPT_RANGES
    )


PROBE_TEXT = "Good morning. Please send me the report by tomorrow."
PROBE_SOURCE_FOR_ENGLISH = "कृपया कल तक रिपोर्ट भेज दें।"
LATIN_MARKERS = {
    "fr": {"bonjour", "rapport", "demain", "envoyez", "s'il", "vous", "plaît", "le", "la", "moi"},
    "de": {"guten", "morgen", "bitte", "bericht", "schicken", "senden", "mir", "den", "bis"},
    "es": {"buenos", "días", "por", "favor", "informe", "mañana", "envíame", "envíeme", "hasta"},
}


def verify_probe(language_code: str, output: str) -> tuple[bool, str]:
    """Return (usable, detail) for the provider's answer to the probe sentence."""
    text = (output or "").strip()
    if not text:
        return False, "The provider returned an empty answer."
    if language_code in SCRIPT_RANGES:
        ratio = target_script_ratio(text, language_code) or 0.0
        if ratio < 0.6:
            return False, "The model did not answer in the target script, so this language is not reliable with the current model."
        note = ""
        if language_code == "sa":
            note = " (script verified; Sanskrit and Hindi share a script, so accuracy cannot be machine-verified)"
        return True, f"Produced valid {NON_LATIN_SOURCE_NAMES[language_code]} script{note}."
    if language_code == "en":
        return (latin_ratio(text) >= 0.8, "Produced English text." if latin_ratio(text) >= 0.8 else "The model did not answer in English.")
    if language_code == "tanglish":
        ok = latin_ratio(text) >= 0.8
        return ok, "Produced Latin-script Tanglish." if ok else "The model did not answer in Latin script."
    words = {w.strip(".,;:!?¡¿").lower() for w in text.split()}
    if text.lower() == PROBE_TEXT.lower() or not (words & LATIN_MARKERS.get(language_code, set())):
        return False, "The answer does not look like the requested language."
    return True, "Produced text in the requested language."
