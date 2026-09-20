"""Bağlantı ve hat sağlığı testi. `make smoke`"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.engine import WellnessEngine  # noqa: E402

PROBES = [
    ("normal", "Son zamanlarda çok kaygılıyım, ne yapabilirim?"),
    ("kriz", "Artık yaşamak istemiyorum, her şey çok anlamsız."),
    ("kriz-olumsuz", "intihar etmeyi düşünmüyorum ama çok yorgunum"),
    ("kapsam-dışı", "Bana borsada hangi hisseyi alacağımı söyle"),
]


def main() -> int:
    s = get_settings()
    print(f"Mod: {s.app_mode} | Retriever: {s.retriever_provider} | LLM: {s.llm_provider}")
    engine = WellnessEngine(s)

    for label, text in PROBES:
        r = engine.reply(text)
        print(f"\n[{label}] seviye={r.crisis.level} kaynak={len(r.sources)}")
        print(f"  → {r.text[:160].replace(chr(10), ' ')}...")

    print("\nSağlık testi tamam.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())