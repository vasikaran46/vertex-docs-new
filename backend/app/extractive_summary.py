"""Offline, dependency-free extractive summarizer.

The summary is built from sentences of the original document, so a Tamil
document produces a Tamil summary and a Hindi document produces a Hindi
summary without any translation step or language model.

Scoring is a classic frequency-based extractive method:

* split the document into sentences using script-aware punctuation
  (``.``, ``!``, ``?``, the Devanagari danda ``।`` and ``॥``);
* score every sentence by the frequency of its content words;
* favour the opening sentences slightly and sentences that contain
  numbers or dates;
* select the highest scoring sentences until the length budget is met;
* put the selected sentences back in their original order.

No network access, model download, or third-party package is involved.
"""

import math
import re

# Sentence-ending punctuation used by the languages Vertex supports.
_SENTENCE_END = ".!?।॥…"
_CLOSING_QUOTES = "\"'”’)]}»"
_WORD_PATTERN = re.compile(r"[^\s.,!?;:।॥…\"'“”‘’()\[\]{}\-/\\|<>*_=+~`]+")
_SENTENCE_SPLIT = re.compile(rf"(?<=[{re.escape(_SENTENCE_END)}])[\s]+")
_BLANK_LINE = re.compile(r"\n\s*\n")

# A compact stop-word list for English, Tamil, and Hindi. Words not listed
# still count; the list only stops very common grammar words from dominating.
STOP_WORDS = {
    # English
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "so", "to", "of",
    "in", "on", "at", "by", "for", "with", "from", "as", "is", "are", "was", "were",
    "be", "been", "being", "it", "its", "this", "that", "these", "those", "i", "you",
    "he", "she", "we", "they", "them", "his", "her", "their", "our", "my", "your",
    "not", "no", "do", "does", "did", "has", "have", "had", "will", "would", "can",
    "could", "should", "may", "might", "must", "there", "here", "which", "who",
    "whom", "what", "when", "where", "why", "how", "also", "very", "more", "most",
    "some", "any", "all", "each", "such", "into", "about", "up", "down", "out",
    # Tamil
    "ஒரு", "மற்றும்", "என்று", "என்ற", "இது", "அது", "இந்த", "அந்த", "ஆகும்",
    "உள்ள", "உள்ளது", "உள்ளன", "என்பது", "என", "ஆனால்", "அல்லது", "முதல்",
    "வரை", "மிக", "மிகவும்", "பல", "அனைத்து", "அவர்", "அவர்கள்", "நான்", "நீ",
    "நாம்", "நீங்கள்", "என்", "உன்", "என்ன", "ஏன்", "எப்படி", "எங்கே",
    "எப்போது", "யார்", "எனவே", "மேலும்", "இல்லை", "உண்டு", "கொண்டு",
    "செய்து", "விட்டு", "இருக்கிறது", "இருக்கும்", "ஆக", "ஆகவும்", "இருந்து",
    # Hindi
    "है", "हैं", "था", "थे", "थी", "का", "की", "के", "को", "में", "से", "पर",
    "और", "या", "एक", "यह", "वह", "ये", "वे", "कि", "भी", "तो", "ही", "नहीं",
    "न", "हो", "होता", "होती", "होते", "कर", "करने", "किया", "गया", "गई",
    "गए", "द्वारा", "लिए", "साथ", "बहुत", "कुछ", "सभी", "इस", "उस", "जो",
    "कहा", "कहते", "रूप", "अपने", "अपनी", "अपना", "हम", "आप", "वह",
}

MIN_SENTENCE_WORDS = 3
DEFAULT_MIN_CHARS = 360
DEFAULT_MAX_CHARS = 1500
SUMMARY_RATIO = 0.3


def split_sentences(text: str) -> list[str]:
    """Split text into sentences without assuming an English-only document."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
    sentences: list[str] = []
    for block in _BLANK_LINE.split(normalized):
        block = block.replace("\n", " ").strip()
        if not block:
            continue
        for part in _SENTENCE_SPLIT.split(block):
            sentence = part.strip()
            if sentence:
                sentences.append(sentence)
    return sentences


def _words(sentence: str) -> list[str]:
    return [word for word in _WORD_PATTERN.findall(sentence) if any(character.isalnum() for character in word)]


def _sentence_key(sentence: str) -> str:
    return " ".join(word.lower() for word in _words(sentence))


def _summary_budget(text_length: int) -> int:
    if text_length <= DEFAULT_MIN_CHARS:
        return text_length
    budget = int(text_length * SUMMARY_RATIO)
    return max(DEFAULT_MIN_CHARS, min(DEFAULT_MAX_CHARS, budget))


def summarize(text: str, max_chars: int | None = None) -> str:
    """Return an extractive summary written in the document's own language."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    budget = max_chars or _summary_budget(len(cleaned))
    if len(cleaned) <= budget:
        return cleaned

    sentences = split_sentences(cleaned)
    if not sentences:
        return cleaned[:budget].rsplit(" ", 1)[0].strip() or cleaned[:budget]
    if len(sentences) == 1:
        return cleaned[:budget].rsplit(" ", 1)[0].strip() or cleaned[:budget]

    tokenized = [_words(sentence) for sentence in sentences]
    frequencies: dict[str, int] = {}
    for words in tokenized:
        for word in words:
            lowered = word.lower()
            if lowered in STOP_WORDS or len(lowered) == 1:
                continue
            frequencies[lowered] = frequencies.get(lowered, 0) + 1
    if not frequencies:
        frequencies = {word.lower(): 1 for words in tokenized for word in words}
    maximum = max(frequencies.values())

    scored: list[tuple[float, int]] = []
    total = len(sentences)
    for index, (sentence, words) in enumerate(zip(sentences, tokenized)):
        if len(words) < MIN_SENTENCE_WORDS:
            continue
        score = 0.0
        for word in words:
            lowered = word.lower()
            if lowered in STOP_WORDS:
                continue
            score += frequencies.get(lowered, 0) / maximum
        score /= math.sqrt(len(words))
        # Opening sentences usually introduce the topic.
        score *= 1.0 + 0.25 * (1.0 - index / total)
        # Dates, amounts, and figures are usually key details.
        if any(character.isdigit() for character in sentence):
            score *= 1.1
        scored.append((score, index))
    if not scored:
        scored = [(1.0, index) for index in range(total)]

    scored.sort(key=lambda item: item[0], reverse=True)
    selected: list[int] = []
    seen: set[str] = set()
    used = 0
    minimum_sentences = min(3, len(scored))
    for score, index in scored:
        if len(selected) >= minimum_sentences and used >= budget:
            break
        key = _sentence_key(sentences[index])
        if not key or key in seen:
            continue
        length = len(sentences[index])
        if selected and used + length > budget * 1.15:
            continue
        selected.append(index)
        seen.add(key)
        used += length
        if used >= budget and len(selected) >= minimum_sentences:
            break

    if not selected:
        return cleaned[:budget].rsplit(" ", 1)[0].strip() or cleaned[:budget]
    selected.sort()
    summary = " ".join(sentences[index] for index in selected).strip()
    if len(summary) > budget * 1.3:
        summary = summary[: int(budget * 1.3)].rsplit(" ", 1)[0].strip()
    return summary
