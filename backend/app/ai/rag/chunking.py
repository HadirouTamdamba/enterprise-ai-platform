"""Configurable chunking strategies (F-22). Pure functions — easy to test and extend."""

import re
from dataclasses import dataclass, field

from app.domain.entities.ai import ChunkingStrategy


@dataclass(slots=True)
class TextChunk:
    content: str
    index: int
    page: int | None = None
    metadata: dict = field(default_factory=dict)


def chunk_text(
    text: str,
    *,
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    page: int | None = None,
) -> list[TextChunk]:
    text = text.strip()
    if not text:
        return []
    if strategy == ChunkingStrategy.FIXED:
        pieces = _fixed(text, chunk_size, chunk_overlap)
    elif strategy == ChunkingStrategy.MARKDOWN:
        pieces = _markdown(text, chunk_size, chunk_overlap)
    elif strategy == ChunkingStrategy.SEMANTIC:
        pieces = _semantic(text, chunk_size)
    else:
        pieces = _recursive(text, chunk_size, chunk_overlap)
    return [
        TextChunk(content=piece, index=i, page=page)
        for i, piece in enumerate(pieces)
        if piece.strip()
    ]


def _fixed(text: str, size: int, overlap: int) -> list[str]:
    step = max(size - overlap, 1)
    return [text[i : i + size] for i in range(0, len(text), step)]


_SEPARATORS = ["\n\n", "\n", ". ", " "]


def _recursive(text: str, size: int, overlap: int, depth: int = 0) -> list[str]:
    """Split on the coarsest separator that produces pieces under the size limit."""
    if len(text) <= size:
        return [text]
    if depth >= len(_SEPARATORS):
        return _fixed(text, size, overlap)
    parts = text.split(_SEPARATORS[depth])
    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = (current + _SEPARATORS[depth] + part) if current else part
        if len(candidate) <= size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(part) > size:
                chunks.extend(_recursive(part, size, overlap, depth + 1))
                current = ""
            else:
                current = part
    if current:
        chunks.append(current)
    return chunks


def _markdown(text: str, size: int, overlap: int) -> list[str]:
    """Split on headings first so sections stay coherent, then recursively."""
    sections = re.split(r"(?=^#{1,4}\s)", text, flags=re.MULTILINE)
    chunks: list[str] = []
    for section in sections:
        if not section.strip():
            continue
        chunks.extend(_recursive(section, size, overlap) if len(section) > size else [section])
    return chunks


def _semantic(text: str, size: int) -> list[str]:
    """Sentence-boundary grouping targeting `size` characters per chunk.

    A lightweight semantic approximation: sentences are never split, and topic
    shifts (paragraph breaks) start new chunks early.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        for sentence in sentences:
            if current and len(current) + len(sentence) > size:
                chunks.append(current.strip())
                current = ""
            current += (" " if current else "") + sentence
        # Paragraph boundary: close the chunk if it is already substantial.
        if len(current) > size * 0.6:
            chunks.append(current.strip())
            current = ""
    if current.strip():
        chunks.append(current.strip())
    return chunks
