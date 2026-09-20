"""Kriz tespiti ve yükseltme (escalation).

İKİ KATMANLI TASARIM:
  1. Kural tabanlı ön filtre  — her mesajda çalışır, API çağrısı yok,
     sıfır gecikme, ücretsiz.
  2. (Opsiyonel) LLM sınıflandırıcı — ikinci görüş.

KURAL TABANLI KATMAN BİRİNCİL KAPIDIR. LLM katmanı kapalıyken de
sistem çalışır durumda kalmalıdır.

UYARI: Anahtar kelime listesi klinik olarak doğrulanmamıştır.
Hem yanlış pozitif (gereksiz alarm) hem yanlış negatif (kaçırılan
kriz) üretir. Partner bu listeyi gözden geçirmeli ve genişletmelidir.
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .schemas import CrisisAssessment, CrisisLevel

log = logging.getLogger(__name__)

_LEVEL_ORDER: list[CrisisLevel] = ["none", "elevated", "high", "critical"]


def _downgrade(level: CrisisLevel) -> CrisisLevel:
    idx = _LEVEL_ORDER.index(level)
    return _LEVEL_ORDER[max(0, idx - 1)]


class CrisisDetector:
    def __init__(self, protocol_path: Path) -> None:
        self.protocol_path = protocol_path
        self.protocol = self._load(protocol_path)

        self.critical_terms = [t.lower() for t in self.protocol.get("critical", {}).get("keywords", [])]
        self.high_terms = [t.lower() for t in self.protocol.get("high", {}).get("keywords", [])]
        self.negations = [t.lower() for t in self.protocol.get("negation_cues", [])]
        self.critical_message = self.protocol.get("critical", {}).get("message", "").strip()
        self.high_message = self.protocol.get("high", {}).get("message", "").strip()

        if self.protocol.get("meta", {}).get("reviewed_by", "BEKLENİYOR") == "BEKLENİYOR":
            log.warning(
                "KRİZ PROTOKOLÜ HENÜZ KLİNİK OLARAK ONAYLANMADI. "
                "Gerçek kullanıcılara açmadan önce %s dosyasını gözden geçirin.",
                protocol_path,
            )

    @staticmethod
    def _load(path: Path) -> dict:
        if not path.exists():
            log.error("Kriz protokolü bulunamadı: %s — boş protokol kullanılıyor.", path)
            return {}
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _is_negated(self, text_lower: str, term: str) -> bool:
        """Anahtar kelimeden sonraki 45 karakterde olumsuzlama var mı?"""
        pos = text_lower.find(term)
        if pos == -1:
            return False
        window = text_lower[pos + len(term): pos + len(term) + 45]
        return any(cue in window for cue in self.negations)

    def _message_for(self, level: CrisisLevel) -> str:
        raw = self.critical_message if level == "critical" else self.high_message
        extra = self.protocol.get("ek_kaynaklar", "").strip()
        return raw.replace("{ek_kaynaklar}", extra)

    def assess(self, text: str) -> CrisisAssessment:
        if not text or not text.strip():
            return CrisisAssessment()

        low = text.lower()
        matched: list[str] = []

        for term in self.critical_terms:
            if term in low:
                if self._is_negated(low, term):
                    matched.append(f"{term} (olumsuzlanmış)")
                    continue
                matched.append(term)
                return CrisisAssessment(
                    level="critical",
                    matched_terms=matched,
                    message=self._message_for("critical"),
                )

        for term in self.high_terms:
            if term in low:
                matched.append(term)

        if matched:
            return CrisisAssessment(
                level="high",
                matched_terms=matched,
                message=self._message_for("high"),
            )

        return CrisisAssessment()

    # ── Opsiyonel ikinci katman ──────────────────────────────────
    def assess_with_llm(
        self, text: str, llm_callable, on_error: str = "escalate"
    ) -> CrisisAssessment:
        """LLM ikinci görüşü. Hata durumunda davranış yapılandırılabilir.

        on_error='escalate'    → güvenli taraf (daha fazla yanlış pozitif)
        on_error='pass_through'→ yalnızca kural katmanına güven

        Bu bir KLİNİK KARARDIR. Partner seçmelidir.
        """
        rule = self.assess(text)
        if rule.level == "critical":
            return rule
        try:
            verdict = llm_callable(text)  # "critical" | "high" | "none"
            if verdict in ("critical", "high"):
                level: CrisisLevel = verdict  # type: ignore[assignment]
                return CrisisAssessment(
                    level=level,
                    matched_terms=rule.matched_terms + [f"llm:{verdict}"],
                    message=self._message_for(level),
                )
            return rule
        except Exception:  # noqa: BLE001
            log.exception("LLM kriz sınıflandırıcı hata verdi")
            if on_error == "escalate":
                return CrisisAssessment(
                    level="high",
                    matched_terms=rule.matched_terms + ["llm:error"],
                    message=self._message_for("high"),
                )
            return rule