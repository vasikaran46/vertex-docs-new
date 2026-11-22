"""Offline humanizer: rewrites stiff / machine-sounding English into natural prose.

It never invents content. It only
  * swaps wordy or cliché phrases for plain ones (tense-safe),
  * applies (or expands) contractions depending on the chosen style,
  * breaks up very long sentences and varies repeated transition words (higher strengths).

It is the guaranteed fallback when no chat model is configured or the model fails,
so the Humanizer page always produces a result.
"""

from __future__ import annotations

import re

# (regex, replacement). Matched with \b ... \b, case-insensitive; first-letter case is preserved.
_ALWAYS: list[tuple[str, str]] = [
    (r"in order to", "to"),
    (r"due to the fact that", "because"),
    (r"owing to the fact that", "because"),
    (r"in spite of the fact that", "although"),
    (r"despite the fact that", "although"),
    (r"in the event that", "if"),
    (r"at this point in time", "now"),
    (r"at the present time", "now"),
    (r"for the purpose of", "for"),
    (r"with regard to", "about"),
    (r"with respect to", "about"),
    (r"in relation to", "about"),
    (r"a (?:plethora|myriad|multitude) of", "many"),
    (r"a number of", "several"),
    (r"is able to", "can"),
    (r"are able to", "can"),
    (r"has the ability to", "can"),
    (r"have the ability to", "can"),
    (r"delve into", "look into"), (r"delves into", "looks into"), (r"delved into", "looked into"), (r"delving into", "looking into"),
    (r"navigate the complexities of", "deal with"),
    (r"rich tapestry of", "mix of"),
    (r"game[- ]changer", "big change"),
    (r"paradigm shift", "major shift"),
    (r"prior to", "before"),
    (r"subsequent to", "after"),
    (r"in close proximity to", "near"),
    (r"on a daily basis", "daily"),
    (r"on a regular basis", "regularly"),
    (r"in the near future", "soon"),
    (r"as a matter of fact", "in fact"),
    (r"each and every", "every"),
    (r"first and foremost", "first"),
    (r"last but not least", "finally"),
    (r"utili[sz]ation", "use"),
    (r"utili[sz]e", "use"), (r"utili[sz]es", "uses"), (r"utili[sz]ed", "used"), (r"utili[sz]ing", "using"),
    (r"commence", "start"), (r"commences", "starts"), (r"commenced", "started"), (r"commencing", "starting"),
    (r"endeavou?rs? to", "try to"), (r"endeavou?red to", "tried to"), (r"endeavou?ring to", "trying to"),
    (r"facilitate", "help"), (r"facilitates", "helps"), (r"facilitated", "helped"), (r"facilitating", "helping"),
    (r"numerous", "many"),
    (r"approximately", "about"),
    (r"subsequently", "later"),
]

_CASUAL: list[tuple[str, str]] = [
    (r"demonstrate", "show"), (r"demonstrates", "shows"), (r"demonstrating", "showing"),
    (r"obtain", "get"), (r"obtains", "gets"), (r"obtaining", "getting"),
    (r"terminate", "end"), (r"terminates", "ends"), (r"terminated", "ended"), (r"terminating", "ending"),
    (r"attempted to", "tried to"), (r"attempting to", "trying to"),
    (r"individuals", "people"),
]

# Removed when they open a sentence (capitalising what follows) or appear mid-sentence.
_FILLER_PHRASES = [
    r"it is (?:important|worth) (?:to note|noting|to mention|to remember) that",
    r"it should be noted that",
    r"it goes without saying that",
    r"needless to say",
]

# Sentence-opening swaps: (regex, replacement, only_for_casual_styles)
_OPENERS: list[tuple[str, str, bool]] = [
    (r"in today'?s (?:fast[- ]paced |modern |digital |ever[- ]changing )?(?:world|era|landscape|age)", "Today", False),
    (r"in conclusion", "To wrap up", True),
    (r"to sum up", "In short", True),
    (r"furthermore", "Also", True),
    (r"moreover", "Also", True),
    (r"additionally", "Also", True),
    (r"consequently", "So", True),
    (r"therefore", "So", True),
    (r"nevertheless", "Still", True),
    (r"nonetheless", "Still", True),
]

_CONTRACT_ALWAYS: list[tuple[str, str]] = [
    (r"\bcannot\b", "can't"), (r"\bwill not\b", "won't"), (r"\bdo not\b", "don't"), (r"\bdoes not\b", "doesn't"),
    (r"\bdid not\b", "didn't"), (r"\bis not\b", "isn't"), (r"\bare not\b", "aren't"), (r"\bwas not\b", "wasn't"),
    (r"\bwere not\b", "weren't"), (r"\bhave not\b", "haven't"), (r"\bhas not\b", "hasn't"), (r"\bhad not\b", "hadn't"),
    (r"\bwould not\b", "wouldn't"), (r"\bshould not\b", "shouldn't"), (r"\bcould not\b", "couldn't"),
]
# Pronoun contractions only at the start of a clause, so "what it is" / "who we are" are never broken.
_CLAUSE_START = r"(?P<lead>^|[.!?]\s+|,\s+|\b(?:and|but|so|because|if|when|while)\s+)"
_CONTRACT_PRONOUN: list[tuple[str, str]] = [
    (r"it is", "it's"), (r"that is", "that's"), (r"there is", "there's"), (r"we are", "we're"),
    (r"they are", "they're"), (r"you are", "you're"), (r"I am", "I'm"), (r"we will", "we'll"),
    (r"I will", "I'll"), (r"you will", "you'll"), (r"they will", "they'll"),
]
_EXPAND: list[tuple[str, str]] = [
    (r"\bcan't\b", "cannot"), (r"\bwon't\b", "will not"), (r"\bdon't\b", "do not"), (r"\bdoesn't\b", "does not"),
    (r"\bdidn't\b", "did not"), (r"\bisn't\b", "is not"), (r"\baren't\b", "are not"), (r"\bwasn't\b", "was not"),
    (r"\bweren't\b", "were not"), (r"\bhaven't\b", "have not"), (r"\bhasn't\b", "has not"), (r"\bhadn't\b", "had not"),
    (r"\bwouldn't\b", "would not"), (r"\bshouldn't\b", "should not"), (r"\bcouldn't\b", "could not"),
    (r"\bit's (?=been|got)", "it has "), (r"\bthat's (?=been|got)", "that has "), (r"\bthere's (?=been)", "there has "),
    (r"\bit's\b", "it is"), (r"\bthat's\b", "that is"), (r"\bthere's\b", "there is"), (r"\bwe're\b", "we are"),
    (r"\bthey're\b", "they are"), (r"\byou're\b", "you are"), (r"\bI'm\b", "I am"), (r"\bwe'll\b", "we will"),
    (r"\bI'll\b", "I will"), (r"\byou'll\b", "you will"), (r"\bthey'll\b", "they will"),
]

_LEADING_TRANSITIONS = ["Also,", "Plus,", "On top of that,", "What's more,", "Beyond that,"]
_TRANSITION_RE = re.compile(r"^(Also|Furthermore|Moreover|Additionally),\s+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")
_SUBJECTS = {"i", "we", "you", "they", "he", "she", "it", "this", "that", "these", "those", "the", "a", "an",
             "our", "their", "his", "her", "its", "there", "many", "some", "most", "my", "your"}


def _match_case(found: str, replacement: str) -> str:
    if found[:1].isupper() and replacement[:1].islower():
        return replacement[:1].upper() + replacement[1:]
    return replacement


_PARTICIPLE_LEAD = r"(?:has|have|had|been|being|is|are|was|were|be)"


def _demonstrated(text: str) -> tuple[str, int]:
    """'demonstrated' -> 'shown' after an auxiliary (has demonstrated), else 'showed'."""
    text, a = re.subn(rf"\b({_PARTICIPLE_LEAD}) demonstrated\b", lambda m: m.group(1) + " shown", text, flags=re.I)
    text, b = re.subn(r"\bdemonstrated\b", lambda m: _match_case(m.group(0), "showed"), text, flags=re.I)
    return text, a + b


def _swap(table: list[tuple[str, str]], text: str) -> tuple[str, int]:
    total = 0
    for pattern, replacement in table:
        text, count = re.subn(rf"\b(?:{pattern})\b", lambda m, r=replacement: _match_case(m.group(0), r), text, flags=re.I)
        total += count
    return text, total


def _drop_fillers(text: str) -> tuple[str, int]:
    total = 0
    for phrase in _FILLER_PHRASES:
        text, count = re.subn(
            rf"(^|(?<=[.!?])\s+)(?:{phrase}),?\s+(\w)",
            lambda m: m.group(1) + m.group(2).upper(),
            text, flags=re.I | re.M,
        )
        total += count
        text, count = re.subn(rf"\b(?:{phrase}),?\s+", "", text, flags=re.I)
        total += count
    return text, total


def _swap_openers(text: str, casual: bool) -> tuple[str, int]:
    total = 0
    for pattern, replacement, casual_only in _OPENERS:
        if casual_only and not casual:
            continue
        text, count = re.subn(
            rf"(^|(?<=[.!?])\s+)(?:{pattern}),?\s+",
            lambda m, r=replacement: m.group(1) + r + ", ",
            text, flags=re.I | re.M,
        )
        total += count
    return text, total


def _contract(text: str) -> tuple[str, int]:
    text = text.replace("’", "'")
    total = 0
    for pattern, replacement in _CONTRACT_ALWAYS:
        text, count = re.subn(pattern, lambda m, r=replacement: _match_case(m.group(0), r), text, flags=re.I)
        total += count

    def pronoun(match: re.Match, replacement: str) -> str:
        lead = match.group("lead")
        starts_sentence = lead == "" or lead.strip()[-1:] in ".!?" if lead.strip() or lead == "" else False
        return lead + (replacement[:1].upper() + replacement[1:] if starts_sentence else replacement)

    for phrase, replacement in _CONTRACT_PRONOUN:
        text, count = re.subn(
            rf"{_CLAUSE_START}{phrase}(?=\s+(?!not\b)\w)",
            lambda m, r=replacement: pronoun(m, r),
            text, flags=re.M | re.I,
        )
        total += count
    return text, total


def _expand(text: str) -> tuple[str, int]:
    text = text.replace("’", "'")
    total = 0
    for pattern, replacement in _EXPAND:
        text, count = re.subn(pattern, lambda m, r=replacement: _match_case(m.group(0), r), text, flags=re.I)
        total += count
    return text, total


def _fix_spacing(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([,.;:!?])", r"\1", text)
    text = re.sub(r",\s*,", ",", text)
    return text.strip()


def _split_long_sentences(paragraph: str, limit: int) -> tuple[str, int]:
    changed = 0
    out: list[str] = []
    for sentence in _SENTENCE_RE.split(paragraph):
        if len(sentence.split()) <= limit:
            out.append(sentence)
            continue
        middle = len(sentence) / 2
        options = []
        for m in re.finditer(r"(?:, (and|but|so) |; )", sentence):
            head, tail = sentence[: m.start()], sentence[m.end():]
            first = tail.split(" ", 1)[0].lower().strip(",")
            if len(head.split()) < 8 or len(tail.split()) < 8:
                continue
            if m.group(0) == "; " or first in _SUBJECTS:
                options.append(m)
        if not options:
            out.append(sentence)
            continue
        best = min(options, key=lambda m: abs(m.start() - middle))
        head = sentence[: best.start()].rstrip(",;")
        tail = sentence[best.end():]
        joiner = (best.group(1) or "").lower()
        head += "" if head.endswith((".", "!", "?")) else "."
        tail = (joiner.capitalize() + " " + tail) if joiner in {"but", "so"} else tail[:1].upper() + tail[1:]
        out.extend([head, tail])
        changed += 1
    return " ".join(out), changed


def _vary_transitions(paragraphs: list[str]) -> tuple[list[str], int]:
    index = 0
    edits = 0
    result = []
    for paragraph in paragraphs:
        fixed = []
        for sentence in _SENTENCE_RE.split(paragraph):
            match = _TRANSITION_RE.match(sentence)
            if match:
                replacement = _LEADING_TRANSITIONS[index % len(_LEADING_TRANSITIONS)]
                if replacement != match.group(1) + ",":
                    edits += 1
                sentence = replacement + " " + sentence[match.end():]
                index += 1
            fixed.append(sentence)
        result.append(" ".join(fixed))
    return result, edits


def humanize_local(text: str, style: str = "simple", strength: int = 3) -> tuple[str, int]:
    """Return ``(rewritten_text, number_of_edits)`` for English text."""
    edits = 0
    casual = style in {"simple", "conversational"}
    blocks: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        lines = []
        for line in paragraph.split("\n"):
            current = line
            current, n = _drop_fillers(current); edits += n
            current, n = _swap(_ALWAYS, current); edits += n
            current, n = _swap_openers(current, casual and strength >= 2); edits += n
            if casual and strength >= 2:
                current, n = _demonstrated(current); edits += n
                current, n = _swap(_CASUAL, current); edits += n
            if style == "conversational" or (style == "simple" and strength >= 3):
                current, n = _contract(current); edits += n
            elif style in {"academic", "professional"}:
                current, n = _expand(current); edits += n
            lines.append(_fix_spacing(current))
        block = "\n".join(lines)
        if strength >= 3 and "\n" not in block:
            block, n = _split_long_sentences(block, 34 if strength == 3 else 24 if strength == 4 else 18)
            edits += n
        blocks.append(block)
    if strength >= 4 and casual:
        blocks, n = _vary_transitions(blocks)
        edits += n
    return "\n\n".join(blocks).strip(), edits


def looks_non_english(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if ord(c) < 0x250) / len(letters) < 0.6


_PREAMBLE_RE = re.compile(r"^(?:sure|certainly|here(?:'s| is)|of course)[^\n]*:\s*\n+", re.I)


def clean_model_output(text: str) -> str:
    """Strip chatty preambles / code fences that chat models like to add."""
    value = text.strip()
    value = re.sub(r"^```[a-z]*\n|\n```$", "", value).strip()
    value = _PREAMBLE_RE.sub("", value).strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"“":
        value = value[1:-1].strip()
    return value
