"""Unit tests for chunking strategies."""

from app.ai.rag.chunking import chunk_text
from app.domain.entities.ai import ChunkingStrategy


def test_fixed_chunking_respects_size():
    chunks = chunk_text("a" * 2500, strategy=ChunkingStrategy.FIXED, chunk_size=1000,
                        chunk_overlap=100)
    assert all(len(c.content) <= 1000 for c in chunks)
    assert len(chunks) >= 3


def test_recursive_prefers_paragraph_boundaries():
    text = "First paragraph about topic A.\n\nSecond paragraph about topic B.\n\n" + "C" * 50
    chunks = chunk_text(text, strategy=ChunkingStrategy.RECURSIVE, chunk_size=60,
                        chunk_overlap=0)
    assert any("topic A" in c.content for c in chunks)
    assert all(len(c.content) <= 60 for c in chunks)


def test_markdown_keeps_sections_together():
    text = "# Intro\nShort intro.\n\n# Details\nMore details here."
    chunks = chunk_text(text, strategy=ChunkingStrategy.MARKDOWN, chunk_size=500,
                        chunk_overlap=0)
    assert len(chunks) == 2
    assert chunks[0].content.startswith("# Intro")


def test_semantic_never_splits_sentences():
    text = "This is sentence one. This is sentence two. " * 30
    chunks = chunk_text(text, strategy=ChunkingStrategy.SEMANTIC, chunk_size=200)
    for chunk in chunks:
        assert chunk.content.rstrip().endswith((".", "!", "?"))


def test_empty_text_returns_no_chunks():
    assert chunk_text("   ") == []


def test_chunks_carry_index_and_page():
    chunks = chunk_text("word " * 500, chunk_size=300, chunk_overlap=50, page=7)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(c.page == 7 for c in chunks)
