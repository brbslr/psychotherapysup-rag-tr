"""Orkestratör: redaksiyon → kriz tespiti → geri getirme → üretim."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from .config import Settings
from .crisis import CrisisDetector
from .llm import build_llm
from .prompt import NO_CONTEXT_REPLY, format_context
from .redaction import Redactor
from .retrieval import build_retriever
from .schemas import EngineReply

log = logging.getLogger(__name__)


class WellnessEngine:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.redactor = Redactor()
        self.crisis = CrisisDetector(settings.crisis_protocol_path)
        self.retriever = build_retriever(settings)
        self.llm = build_llm(settings)

    # ── Ana giriş noktası ────────────────────────────────────────
    def reply(self, message: str, history: list[dict] | None = None) -> EngineReply:
        history = history or []
        degraded = False

        # 1) KVKK: tanımlayıcıları temizle
        red = self.redactor.redact(message) if self.s.redact_enabled else None
        safe_text = red.text if red else message

        # 2) Kriz tespiti (redakte edilmiş metin üzerinde)
        assessment = self.crisis.assess(safe_text)
        if self.s.llm_crisis_classifier_enabled:
            assessment = self.crisis.assess_with_llm(
                safe_text,
                llm_callable=self._llm_crisis_call,
                on_error=self.s.crisis_on_classifier_error,
            )

        # 3) Kritik → AI tamamen durur
        if assessment.should_block_ai:
            self._log(safe_text, "", assessment.level, [], blocked=True)
            return EngineReply(
                text=assessment.message,
                sources=[],
                crisis=assessment,
                redaction=red,
                mode=self.s.app_mode,
                degraded=degraded,
            )

        # 4) Geri getirme
        try:
            passages = self.retriever.search(safe_text, top_k=self.s.top_k)
        except Exception:  # noqa: BLE001
            log.exception("Geri getirme hatası")
            passages = []
            degraded = True

        context = format_context(passages)

        # 5) Üretim
        try:
            answer = self.llm.generate(context, safe_text, history)
        except Exception:  # noqa: BLE001
            log.exception("LLM hatası")
            answer = (
                "Şu an teknik bir sorun nedeniyle yanıt üretemiyorum. "
                "Lütfen birazdan tekrar dene."
            )
            degraded = True

        if not passages and answer == NO_CONTEXT_REPLY:
            degraded = degraded or False

        # 6) Yüksek seviye → yönlendirme mesajını başa ekle
        if assessment.level in ("high", "elevated") and assessment.message:
            answer = f"{assessment.message}\n\n---\n\n{answer}"

        self._log(safe_text, answer, assessment.level, passages)
        return EngineReply(
            text=answer,
            sources=passages,
            crisis=assessment,
            redaction=red,
            mode=self.s.app_mode,
            degraded=degraded,
        )

    # ── Opsiyonel LLM kriz sınıflandırıcı ────────────────────────
    def _llm_crisis_call(self, text: str) -> str:
        prompt = (
            "Aşağıdaki Türkçe mesajda intihar düşüncesi, kendine zarar verme "
            "niyeti veya akut psikiyatrik aciliyet var mı? "
            "Yalnızca şu üç kelimeden birini yaz: critical, high, none.\n\n"
            f"Mesaj: {text}"
        )
        if hasattr(self.llm, "client"):
            resp = self.llm.client.chat.completions.create(  # type: ignore[attr-defined]
                model=self.s.azure_openai_chat_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5,
            )
            return (resp.choices[0].message.content or "none").strip().lower()
        return "none"

    # ── Anonim günlük (partner incelemesi için) ──────────────────
    def _log(self, user_text, answer, level, passages, blocked=False) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "crisis_level": level,
            "blocked": blocked,
            "user_chars": len(user_text),
            "answer_chars": len(answer),
            "source_ids": [p.id for p in passages],
            "user_text": user_text,   # redakte edilmiş halidir
            "answer": answer,
        }
        try:
            path = self.s.log_dir / "sessions.jsonl"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001
            log.exception("Günlük yazılamadı")