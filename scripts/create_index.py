"""Azure AI Search indeksini oluşturur.

Türkçe analizör (tr.microsoft) kök indirgeme yapar:
  "kaygı" ≈ "kaygının" ≈ "kaygılı"
Bu olmadan Türkçe aramada ciddi kayıp yaşanır.

NOT: Semantic ranker Free tier'da YOKTUR. Basic ve üzeri gerekir.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from azure.core.credentials import AzureKeyCredential  # noqa: E402
from azure.search.documents.indexes import SearchIndexClient  # noqa: E402
from azure.search.documents.indexes.models import (  # noqa: E402
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from src.config import get_settings  # noqa: E402


def build_index(settings, with_semantic: bool) -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            analyzer_name=settings.azure_search_analyzer,
        ),
        SearchableField(
            name="title",
            type=SearchFieldDataType.String,
            analyzer_name=settings.azure_search_analyzer,
        ),
        SearchableField(
            name="heading_path",
            type=SearchFieldDataType.String,
            analyzer_name=settings.azure_search_analyzer,
        ),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=settings.embedding_dimensions,
            vector_search_profile_name="hnsw-profile",
        ),
    ]

    index = SearchIndex(
        name=settings.azure_search_index,
        fields=fields,
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
            profiles=[
                VectorSearchProfile(
                    name="hnsw-profile", algorithm_configuration_name="hnsw-config"
                )
            ],
        ),
    )

    if with_semantic:
        index.semantic_search = SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name=settings.azure_search_semantic_config,
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="title"),
                        content_fields=[SemanticField(field_name="content")],
                    ),
                )
            ]
        )
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true", help="Varsa sil ve yeniden oluştur")
    parser.add_argument("--semantic", action="store_true", help="Semantic config ekle (Basic+)")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.azure_search_endpoint or not settings.azure_search_key:
        print("HATA: AZURE_SEARCH_ENDPOINT ve AZURE_SEARCH_KEY gerekli.")
        return 1

    client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=AzureKeyCredential(settings.azure_search_key),
    )

    if args.recreate:
        try:
            client.delete_index(settings.azure_search_index)
            print(f"Silindi: {settings.azure_search_index}")
        except Exception:  # noqa: BLE001
            pass

    index = build_index(settings, with_semantic=args.semantic)
    client.create_or_update_index(index)
    print(f"İndeks hazır: {settings.azure_search_index}")
    print(f"Analizör: {settings.azure_search_analyzer}")
    print(f"Semantic: {'açık' if args.semantic else 'kapalı'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())