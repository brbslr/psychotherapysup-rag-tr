"""Central configuration. Everything is env-driven so the same code runs
in free local mode and in Azure mode without edits."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_mode: Literal["local", "azure"] = "local"

    # Retrieval
    retriever_provider: Literal["local", "azure"] = "local"
    top_k: int = 4
    local_index_path: Path = ROOT / "data" / "local_index.jsonl"
    clinical_docs_dir: Path = ROOT / "docs" / "clinical"

    # LLM
    llm_provider: Literal["echo", "ollama", "azure", "gemini", "vertex_tuned"] = "echo"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    temperature: float = 0.3
    max_tokens: int = 2000

    # Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_key: str = ""
    azure_search_index: str = "wellness-knowledge-tr"
    azure_search_analyzer: str = "tr.microsoft"
    azure_search_use_semantic: bool = False
    azure_search_semantic_config: str = "default-semantic"

    # Gemini
    gemini_api_key: str = "AQ.Ab8RN6J-Uup0bBHIkCncPmTCutm71WPLdhT29dTYvywoIrBhmw"
    gemini_model: str = "gemini-3.8-flash"
    

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Document Intelligence
    azure_docintel_endpoint: str = ""
    azure_docintel_key: str = ""

    # Privacy / safety
    redact_enabled: bool = True
    crisis_protocol_path: Path = ROOT / "config" / "crisis_protocol.yaml"
    crisis_on_classifier_error: Literal["escalate", "pass_through"] = "escalate"
    llm_crisis_classifier_enabled: bool = False

    log_dir: Path = ROOT / "logs"

    @property
    def is_free_mode(self) -> bool:
        return self.app_mode == "local"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.log_dir.mkdir(parents=True, exist_ok=True)
    s.local_index_path.parent.mkdir(parents=True, exist_ok=True)
    return s