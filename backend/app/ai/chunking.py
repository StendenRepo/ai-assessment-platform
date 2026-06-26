import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
_LIST_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+")
_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>+\s?")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_EMPHASIS_RE = re.compile(r"[*_`~]+")
_WS_RE = re.compile(r"[ \t]+")


def _clean_line(line: str) -> str:
    line = _LINK_RE.sub(r"\1", line)
    is_heading = bool(_HEADING_RE.match(line))
    line = _HEADING_RE.sub("", line)
    line = _LIST_RE.sub("", line)
    line = _BLOCKQUOTE_RE.sub("", line)
    line = _EMPHASIS_RE.sub("", line)
    line = _WS_RE.sub(" ", line).strip()
    if is_heading and line and line[-1] not in ".!?:":
        line += "."
    return line


def normalize_markdown(text: str) -> str:
    if not text:
        return ""
    paragraphs: list[str] = []
    current: list[str] = []
    for raw in text.splitlines():
        cleaned = _clean_line(raw)
        if not cleaned:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(cleaned)
    if current:
        paragraphs.append(" ".join(current))
    return "\n".join(paragraphs)


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(text or "") if part.strip()]


def _word_count(sentence: str) -> int:
    return len(sentence.split())


def chunk_text(text: str, chunk_size: int = 60, overlap: int = 15) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    overlap = max(0, min(overlap, chunk_size - 1))

    sentences = split_sentences(normalize_markdown(text))
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = _word_count(sentence)
        if current and current_words + words > chunk_size:
            chunks.append(" ".join(current))
            tail: list[str] = []
            tail_words = 0
            for prev in reversed(current):
                if tail and tail_words >= overlap:
                    break
                tail.insert(0, prev)
                tail_words += _word_count(prev)
            current = tail if overlap else []
            current_words = sum(_word_count(s) for s in current)
        current.append(sentence)
        current_words += words

    if current:
        chunks.append(" ".join(current))

    if len(chunks) >= 2 and chunks[-1] in chunks[-2]:
        chunks.pop()

    return chunks
