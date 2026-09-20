from src.ingest import chunk_document, parse_front_matter


def test_front_matter_parsed():
    raw = "---\ntitle: Test\nsource: t.md\n---\n\n# Başlık\nMetin"
    meta, body = parse_front_matter(raw)
    assert meta["title"] == "Test"
    assert body.strip().startswith("# Başlık")


def test_chunk_prepends_heading_path():
    body = "# Kaygı\n\n## Nefes\n\nDört sayarak al, altı sayarak ver. " * 30
    chunks = chunk_document(body, {"title": "Kaygı Rehberi", "source": "k.md"})
    assert chunks
    assert all("Kaygı Rehberi >" in c["heading_path"] for c in chunks)
    assert all(c["content"].startswith("Kaygı Rehberi") for c in chunks)