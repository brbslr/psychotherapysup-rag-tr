"""LLM arka uçları: echo (ücretsiz demo), ollama (yerel, ücretsiz), azure."""
from __future__ import annotations

import logging

import requests

from .config import Settings
from .prompt import NO_CONTEXT_REPLY, SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)


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
        first = context.split("\n\n")[0]
        body = "\n".join(first.split("\n")[1:]).strip()
        return (
            "_(Demo modu — dil modeli kapalı. Aşağıdaki metin, sistemin "
            "klinik dokümanlarınızdan bulduğu en alakalı bölümdür.)_\n\n"
            f"{body[:700]}"
        )


class OllamaLLM:
    """Yerel, ücretsiz LLM. https://ollama.com → `ollama pull llama3.1:8b`"""

    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def generate(self, context: str, question: str, history: list[dict]) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history[-6:]
        messages.append({"role": "user", "content": build_user_prompt(context, question)})

        resp = requests.post(
            f"{self.s.ollama_base_url}/api/chat",
            json={
                "model": self.s.ollama_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.s.temperature},
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


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


def build_llm(settings: Settings):
    if settings.llm_provider == "azure":
        try:
            return AzureLLM(settings)
        except Exception:  # noqa: BLE001
            log.exception("Azure LLM kurulamadı — echo moduna düşülüyor")
    if settings.llm_provider == "ollama":
        return OllamaLLM(settings)
    return EchoLLM()