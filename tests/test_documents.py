from app.services.documents import chunk_text, extract_document


def test_extracts_utf8_text() -> None:
    result = extract_document("notes.txt", b"hello   world\n\n\nsecond line")
    assert result.text == "hello world\n\nsecond line"
    assert result.ocr_used is False


def test_chunks_preserve_all_content() -> None:
    text = " ".join(f"word-{index}" for index in range(100))
    chunks = chunk_text(text, size=120, overlap=20)
    assert len(chunks) > 1
    assert chunks[0].startswith("word-0")
    assert chunks[-1].endswith("word-99")
