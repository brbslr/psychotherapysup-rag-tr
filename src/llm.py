"""LLM arka uçları: echo (ücretsiz demo), ollama (yerel, ücretsiz), azure."""
from __future__ import annotations

import logging

import requests

from .config import Settings
from .prompt import NO_CONTEXT_REPLY, SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)


import re

# Match the blank line that precedes the next "[N] " block marker.
# This is the ONLY reliable way to separate blocks because content
# itself may contain blank lines.
_BLOCK_START = re.compile(r"\n\n(?=\[\d+\]\s)")

from openai import OpenAI
from .retry import retry_on_service_unavailable

class GeminiLLM:
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.client = OpenAI(
            api_key=settings.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        # Use getattr so a missing optional field doesn't crash the app
        self.model_chain = [self.s.gemini_model]
        fallback = getattr(self.s, "gemini_fallback_model", "")
        if fallback:
            self.model_chain.append(fallback)
        log.info(f"Gemini model chain: {self.model_chain}")

    @retry_on_service_unavailable(max_attempts=3)
    def _call_model(self, model_name: str, messages: list) -> str:
        resp = self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=self.s.temperature,
            max_tokens=self.s.max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    def generate(self, context: str, question: str, history: list[dict]) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history[-6:]
        messages.append(
            {"role": "user", "content": build_user_prompt(context, question)}
        )

        last_error = None
        for model_name in self.model_chain:
            try:
                return self._call_model(model_name, messages)
            except Exception as e:
                log.warning(f"Model {model_name} failed: {e}")
                last_error = e
                continue
        raise last_error

class EchoLLM:
    """LLM yok. Yalnızca en alakalı kaynak pasajını döndürür.

    Bu mod, RAG hattının ÇALIŞTIĞINI kanıtlamak için tasarlandı:
    doğru dokümanı buluyor mu? Cevap üretmiyor, bu yüzden klinik risk
    sıfırdır. Partner ile ilk demo için bunu kullanın.
    """

    name = "echo"

    def generate(self, context: str, question: str, history: list[dict]) -> str:
        if not context or context.strip() == "(boş)":
            return NO_CONTEXT_REPLY

        # Split at the block boundary (blank line + "[N] "), not at every
        # blank line inside the content.
        first_block = _BLOCK_START.split(context, maxsplit=1)[0]

        # First line is "[N] label". Everything after is the heading path
        # (from hierarchical chunking) plus the actual body text.
        _, _, body = first_block.partition("\n")
        body = body.strip() or first_block.strip()

        return (
            "_(Demo modu — dil modeli kapalı. Aşağıdaki metin, sistemin "
            "klinik dokümanlarınızdan bulduğu en alakalı bölümdür.)_\n\n"
            f"{body[:900]}"
        )


class OllamaLLM:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def generate(self, context: str, question: str, history: list[dict]) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history[-6:]
        messages.append(
            {"role": "user", "content": build_user_prompt(context, question)}
        )

        headers = {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",   # ← bypass interstitial page
        }

        resp = requests.post(
            f"{self.s.ollama_base_url}/api/chat",
            headers=headers,
            json={
                "model": self.s.ollama_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.s.temperature},
            },
            timeout=120,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
        return clean_model_output(raw)

class AzureLLM:
    name = "azure"

    def __init__(self, settings: Settings) -> None:
        from openai import AzureOpenAI

        self.s = settings
        self.client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
            api_version=settings.azure_openai_api_version,
        )

    def generate(self, context: str, question: str, history: list[dict]) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history[-6:]
        messages.append({"role": "user", "content": build_user_prompt(context, question)})

        resp = self.client.chat.completions.create(
            model=self.s.azure_openai_chat_deployment,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.s.temperature,
            max_tokens=self.s.max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    @retry_on_service_unavailable(max_attempts=5) # <-- Apply decorator
    def generate(self, context: str, question: str, history: list[dict]) -> str:
        # ... (the rest of your generate method)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history[-6:]
        messages.append({"role": "user", "content": build_user_prompt(context, question)})

        resp = self.client.chat.completions.create(
            model=self.s.azure_openai_chat_deployment,
            messages=messages,
            temperature=self.s.temperature,
            max_tokens=self.s.max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()


def build_llm(settings: Settings):
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            log.warning("GEMINI_API_KEY boş — echo moduna düşülüyor")
            return EchoLLM()
        return GeminiLLM(settings)
    if settings.llm_provider == "azure":
        try:
            return AzureLLM(settings)
        except Exception:
            log.exception("Azure LLM kurulamadı — echo moduna düşülüyor")
    if settings.llm_provider == "ollama":
        return OllamaLLM(settings)
    return EchoLLM()