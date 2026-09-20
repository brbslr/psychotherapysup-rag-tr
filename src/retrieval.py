"""İki geri getirme (retrieval) arka ucu.

LocalTfidfRetriever  → ücretsiz, çevrimdışı, Azure hesabı gerekmez.
AzureHybridRetriever → Azure AI Search, Türkçe analizör + hibrit arama.

NEDEN char n-gram TF-IDF? Türkçe eklemeli (agglutinative) bir dildir:
"kaygı", "kaygının", "kaygılı" farklı kelimelerdir ama aynı kökten gelir.
Kelime tabanlı arama bunları kaçırır. Karakter n-gram'ları bu sorunu
büyük ölçüde çözer ve hiçbir bulut servisi gerektirmez.
"""
from __future__ import annotations

import json
import logging
from dataclasses import fields
from pathlib import Path
from typing import Protocol

from .config import Settings
from .schemas import Passage

log = logging.getLogger(__name__)


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 4) -> list[Passage]: ...


# ── Yerel / ücretsiz ─────────────────────────────────────────────
class LocalTfidfRetriever:
    def __init__(self, index_path: Path) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.index_path = index_path
        self.passages: list[Passage] = []
        self._vectorizer = None
        self._matrix = None

        if not index_path.exists():
            log.warning(
                "Yerel indeks bulunamadı: %s — önce `make index` çalıştırın.",
                index_path,
            )
            return

        rows = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        _valid = {f.name for f in fields(Passage)}
        self.passages = [
            Passage(**{k: v for k, v in row.items() if k in _valid}) for row in rows
        ]

        if self.passages:
            corpus = [p.content for p in self.passages]
            self._vectorizer = TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1
            )
            self._matrix = self._vectorizer.fit_transform(corpus)

    @property
    def ready(self) -> bool:
        return bool(self.passages) and self._vectorizer is not None

    def search(self, query: str, top_k: int = 4) -> list[Passage]:
        if not self.ready:
            return []
        from sklearn.metrics.pairwise import cosine_similarity

        q = self._vectorizer.transform([query])  # type: ignore[union-attr]
        sims = cosine_similarity(q, self._matrix)[0]  # type: ignore[arg-type]
        order = sims.argsort()[::-1][:top_k]
        results = []
        for i in order:
            if sims[i] <= 0:
                continue
            p = self.passages[i]
            results.append(
                Passage(
                    id=p.id,
                    content=p.content,
                    title=p.title,
                    source=p.source,
                    heading_path=p.heading_path,
                    score=float(sims[i]),
                )
            )
        return results


# ── Azure AI Search ──────────────────────────────────────────────
class AzureHybridRetriever:
    """Hibrit arama: BM25 (anahtar kelime) + vektör (anlamsal).

    `turkish-rag-eval` bulgularına göre hibrit + hiyerarşik chunking
    en iyi sonucu veriyor. Türkçe analizör (tr.microsoft) kök indirgeme
    yaptığı için tek başına %20+ kazanç sağlıyor.
    """

    def __init__(self, settings: Settings) -> None:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
        from openai import AzureOpenAI

        if not settings.azure_search_endpoint or not settings.azure_search_key:
            raise ValueError("Azure AI Search endpoint/key eksik.")

        self.s = settings
        self.client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            credential=AzureKeyCredential(settings.azure_search_key),
        )
        self.openai = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
            api_version=settings.azure_openai_api_version,
        )

    def _embed(self, text: str) -> list[float]:
        resp = self.openai.embeddings.create(
            model=self.s.azure_openai_embedding_deployment, input=text
        )
        return resp.data[0].embedding

    def search(self, query: str, top_k: int = 4) -> list[Passage]:
        from azure.search.documents.models import VectorizedQuery

        try:
            vector = self._embed(query)
        except Exception:  # noqa: BLE001
            log.exception("Embedding başarısız — yalnızca anahtar kelime araması")
            vector = None

        vector_queries = []
        if vector:
            vector_queries.append(
                VectorizedQuery(
                    vector=vector, k_nearest_neighbors=top_k * 2, fields="embedding"
                )
            )

        kwargs: dict = {
            "search_text": query,
            "top": top_k,
            "vector_queries": vector_queries,
            "select": ["id", "content", "title", "source", "heading_path"],
        }
        # Semantic ranker Basic tier ve üzeri gerektirir. Free tier desteklemez.
        if self.s.azure_search_use_semantic:
            kwargs["query_type"] = "semantic"
            kwargs["semantic_configuration_name"] = self.s.azure_search_semantic_config

        results = self.client.search(**kwargs)
        out: list[Passage] = []
        for r in results:
            out.append(
                Passage(
                    id=r.get("id", ""),
                    content=r.get("content", ""),
                    title=r.get("title", ""),
                    source=r.get("source", ""),
                    heading_path=r.get("heading_path", ""),
                    score=float(r.get("@search.score", 0.0)),
                )
            )
        return out


def build_retriever(settings: Settings) -> Retriever:
    if settings.retriever_provider == "azure":
        try:
            return AzureHybridRetriever(settings)
        except Exception:  # noqa: BLE001
            log.exception("Azure retriever kurulamadı — yerel moda düşülüyor")
    return LocalTfidfRetriever(settings.local_index_path)