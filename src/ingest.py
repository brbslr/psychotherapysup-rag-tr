"""Belge alımı: front matter → başlık bazlı hiyerarşik chunking → kayıt.

HİYERARŞİK CHUNKING NEDEN ÖNEMLİ:
Her parçanın başına belge başlığı ve başlık yolu eklenir. Böylece
"nefes egzersizi" arayan bir kullanıcı, "Kaygı > Bedensel teknikler >
Nefes" yolunu taşıyan parçayı bulur. Bu, `turkish-rag-eval` projesinin
en yüksek doğruluk veren yapılandırmasıdır.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = FRONT_MATTER.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, text[m.end():]


def _window(text: str, max_chars: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []

    chunks, start = [], 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            # Cümle sınırında kes
            for sep in (". ", "! ", "? ", "\n"):
                cut = text.rfind(sep, start + max_chars // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]


def chunk_document(
    body: str, meta: dict, max_chars: int = 900, overlap: int = 150
) -> list[dict]:
    title = meta.get("title", "")
    source = meta.get("source", "")
    doc_id = meta.get("id") or hashlib.sha1(
        (title + source).encode("utf-8")
    ).hexdigest()[:10]

    # Başlıklara göre böl
    sections: list[tuple[str, str]] = []
    matches = list(HEADING.finditer(body))
    if not matches:
        sections.append(("", body))
    else:
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            sections.append((m.group(2).strip(), body[start:end]))

    passages: list[dict] = []
    for heading, section_text in sections:
        heading_path = f"{title} > {heading}" if heading else title
        for j, piece in enumerate(_window(section_text, max_chars, overlap)):
            # Hiyerarşik bağlamı parçanın başına ekle
            enriched = f"{heading_path}\n\n{piece}" if heading_path else piece
            passages.append(
                {
                    "id": f"{doc_id}-{len(passages):03d}",
                    "content": enriched,
                    "title": title,
                    "source": source,
                    "heading_path": heading_path,
                    "chunk_index": j,
                }
            )
    return passages


def load_markdown_dir(docs_dir: Path) -> list[dict]:
    passages: list[dict] = []
    for path in sorted(docs_dir.glob("*.md")):
        if path.name.startswith("00_"):
            continue  # şablon dosyasını atla
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        meta.setdefault("source", path.name)
        chunks = chunk_document(body, meta)
        log.info("%s → %d parça", path.name, len(chunks))
        passages.extend(chunks)
    return passages


def extract_pdf(path: Path, settings) -> str:
    """Azure AI Document Intelligence ile PDF metni çıkar (F0: 500 sayfa/ay ücretsiz)."""
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    from azure.core.credentials import AzureKeyCredential

    client = DocumentIntelligenceClient(
        endpoint=settings.azure_docintel_endpoint,
        credential=AzureKeyCredential(settings.azure_docintel_key),
    )
    poller = client.begin_analyze_document(
        "prebuilt-layout",
        AnalyzeDocumentRequest(bytes_source=path.read_bytes()),
    )
    result = poller.result()
    return result.content or ""


def write_local_index(passages: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for p in passages:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    log.info("Yerel indeks yazıldı: %s (%d parça)", path, len(passages))