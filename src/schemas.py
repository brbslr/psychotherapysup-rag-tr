from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Passage:
    id: str
    content: str
    title: str = ""
    source: str = ""
    score: float = 0.0
    heading_path: str = ""


@dataclass
class RedactionResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def had_identifiers(self) -> bool:
        return bool(self.mapping)


CrisisLevel = Literal["none", "elevated", "high", "critical"]


@dataclass
class CrisisAssessment:
    level: CrisisLevel = "none"
    matched_terms: list[str] = field(default_factory=list)
    message: str = ""
    negated: bool = False

    @property
    def should_block_ai(self) -> bool:
        return self.level == "critical"


@dataclass
class EngineReply:
    text: str
    sources: list[Passage] = field(default_factory=list)
    crisis: CrisisAssessment = field(default_factory=CrisisAssessment)
    redaction: RedactionResult | None = None
    mode: str = "local"
    degraded: bool = False