"""Lightweight, dependency-free passage retrieval for chatting with a document.

Sending a whole document to the model on every question is slow and often exceeds the model's
context window. This picks the passages most relevant to the question (BM25-style scoring),
which keeps prompts small and answers fast, and also powers an offline fallback answer.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .extractive_summary import STOP_WORDS, split_sentences

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text) if len(t) > 1 and t.lower() not in STOP_WORDS]


def make_chunks(text: str, size: int = 900) -> list[str]:
    """Split on paragraphs, then pack paragraphs/sentences into chunks of about ``size`` characters."""
    chunks: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        pieces = [paragraph] if len(paragraph) <= size else split_sentences(paragraph) or [paragraph]
        for piece in pieces:
            if current and len(current) + len(piece) + 1 > size:
                chunks.append(current)
                current = ""
            current = f"{current}\n{piece}".strip() if current else piece
            while len(current) > size * 2:  # a single huge sentence
                chunks.append(current[:size])
                current = current[size:]
    if current:
        chunks.append(current)
    return chunks


def rank_chunks(chunks: list[str], query: str) -> list[tuple[float, int]]:
    query_terms = set(_tokens(query))
    if not chunks:
        return []
    docs = [Counter(_tokens(chunk)) for chunk in chunks]
    lengths = [sum(counter.values()) or 1 for counter in docs]
    average = sum(lengths) / len(lengths)
    n = len(chunks)
    scores: list[tuple[float, int]] = []
    for index, counter in enumerate(docs):
        score = 0.0
        for term in query_terms:
            frequency = counter.get(term, 0)
            if not frequency:
                continue
            containing = sum(1 for other in docs if term in other)
            idf = math.log(1 + (n - containing + 0.5) / (containing + 0.5))
            score += idf * (frequency * 2.2) / (frequency + 1.2 * (0.25 + 0.75 * lengths[index] / average))
        scores.append((score, index))
    return sorted(scores, key=lambda item: item[0], reverse=True)


def relevant_context(text: str, query: str, budget: int = 6000) -> str:
    """Return up to ``budget`` characters of the most relevant passages, in document order.

    Short documents are returned whole. Generic requests ("summarise", "what is this about")
    that match nothing fall back to the opening of the document.
    """
    cleaned = text.strip()
    if len(cleaned) <= budget:
        return cleaned
    chunks = make_chunks(cleaned)
    ranked = [item for item in rank_chunks(chunks, query) if item[0] > 0]
    chosen: list[int] = []
    used = 0
    if not ranked:
        ranked = [(1.0, 0), *[(0.5, i) for i in range(1, len(chunks))]]
    for _, index in ranked:
        if used + len(chunks[index]) > budget and chosen:
            continue
        chosen.append(index)
        used += len(chunks[index])
        if used >= budget:
            break
    if 0 not in chosen and len(chunks[0]) + used <= budget * 1.15:
        chosen.append(0)  # the opening usually carries the title / purpose
    return "\n\n".join(chunks[i] for i in sorted(set(chosen)))


def extractive_answer(text: str, query: str, limit: int = 4) -> str:
    """Offline answer: the sentences that best match the question."""
    sentences = split_sentences(text)
    if not sentences:
        return ""
    terms = set(_tokens(query))
    scored = []
    for index, sentence in enumerate(sentences):
        overlap = len(terms & set(_tokens(sentence)))
        if overlap:
            scored.append((overlap / math.sqrt(len(sentence.split()) + 1), index))
    if not scored:
        return ""
    scored.sort(reverse=True)
    picked = sorted(index for _, index in scored[:limit])
    return " ".join(sentences[i] for i in picked)
