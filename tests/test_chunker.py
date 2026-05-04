from second_brain.ingestion import Document, RecursiveSemanticChunker


def test_chunker_preserves_markdown_code_fence() -> None:
    content = """# Title

Intro paragraph.

```python
def hello() -> str:
    return "world"
```

## Details

More text.
"""
    document = Document(content=content, source="test.md")
    chunks = RecursiveSemanticChunker(chunk_size=220, chunk_overlap=40).chunk_document(document)

    assert chunks
    assert any("```python" in chunk.content and "return \"world\"" in chunk.content for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunker_splits_long_plain_text_with_overlap() -> None:
    content = " ".join(f"sentence {index}." for index in range(200))
    document = Document(content=content, source="test.txt")
    chunks = RecursiveSemanticChunker(chunk_size=300, chunk_overlap=50).chunk_document(document)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 350 for chunk in chunks)
