from pathlib import Path

import pytest

from src.crisis import CrisisDetector

PROTOCOL = Path(__file__).resolve().parent.parent / "config" / "crisis_protocol.yaml"


@pytest.fixture
def detector():
    return CrisisDetector(PROTOCOL)


def test_critical_phrase_triggers_block(detector):
    a = detector.assess("Artık yaşamak istemiyorum.")
    assert a.level == "critical"
    assert a.should_block_ai


def test_negated_phrase_does_not_block(detector):
    a = detector.assess("intihar etmeyi düşünmüyorum ama çok yorgunum")
    assert not a.should_block_ai


def test_neutral_message_returns_none(detector):
    a = detector.assess("Bugün hava çok güzel.")
    assert a.level == "none"


def test_message_contains_emergency_number(detector):
    a = detector.assess("kendime zarar vermek istiyorum")
    assert "112" in a.message