"""Klinik dokümanları parçalar, (Azure modunda) embed eder ve yükler.

Her zaman `data/local_index.jsonl` yazar — böylece Azure olmadan da
yerel modda arama çalışır.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.ingest import (  # noqa: E402
    extract_pdf,
    load_markdown_dir,
    parse_front_matter,
    chunk_document,
    write_local_index,
)


def upload_to_azure(passages, settings, batch_size: int = 50) -> None:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from openai import AzureOpenAI

    search = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=AzureKeyCredential(settings.azure_search_key),
    )
    openai_client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_key,
        api_version=settings.azure_openai_api_version,
    )

    # Embedding'leri toplu halde üret (maliyeti düşürür)
    for i in range(0, len(passages), batch_size):
        batch = passages[i : i + batch_size]
        resp = openai_client.embeddings.create(
            model=settings.azure_openai_embedding_deployment,
            input=[p["content"] for p in batch],
        )
        for p, emb in zip(batch, resp.data):
            p["embedding"] = emb.embedding

        # Azure AI Search'te olmayan alanları çıkar
        docs = [
            {k: v for k, v in p.items() if k != "chunk_index" or True} for p in batch
        ]
        search.upload_documents(documents=docs)
        print(f"  yüklendi: {i + len(batch)}/{len(passages)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", action="append", default=[], help="İşlenecek PDF yolu")
    parser.add_argument("--upload", action="store_true", help="Azure'a yükle")
    args = parser.parse_args()

    settings = get_settings()
    passages = load_markdown_dir(settings.clinical_docs_dir)
    print(f"Markdown: {len(passages)} parça")

    for pdf in args.pdf:
        path = Path(pdf)
        print(f"PDF işleniyor: {path.name}")
        text = extract_pdf(path, settings)
        meta = {"title": path.stem, "source": path.name}
        chunks = chunk_document(text, meta)
        passages.extend(chunks)
        print(f"  → {len(chunks)} parça")

    if not passages:
        print("UYARI: Hiç parça üretilmedi. docs/clinical/ içine doküman ekleyin.")
        return 0

    write_local_index(passages, settings.local_index_path)

    if args.upload:
        if not settings.azure_search_endpoint:
            print("HATA: --upload için Azure ayarları gerekli.")
            return 1
        print("Azure AI Search'e yükleniyor...")
        upload_to_azure(passages, settings)
        print("Tamamlandı.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())