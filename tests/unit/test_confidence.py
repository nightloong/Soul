from datetime import UTC, datetime, timedelta

from personaforge.distillation.merge import EvidenceSignal, calculate_confidence

NOW = datetime(2026, 9, 28, tzinfo=UTC)


def signal(
    relation: str = "support",
    evidence_type: str = "direct_behavior",
    conversation: str = "one",
    when: datetime = NOW,
) -> EvidenceSignal:
    return EvidenceSignal(relation, evidence_type, 0.75, conversation, when)


def test_single_behavior_remains_weak() -> None:
    assert calculate_confidence([signal()], NOW) == 0.35


def test_explicit_statement_has_high_base_but_personality_is_capped() -> None:
    evidence = [signal(evidence_type="explicit_self_statement")]
    assert calculate_confidence(evidence, NOW) == 0.85
    assert calculate_confidence(evidence, NOW, high_level_personality=True) == 0.6


def test_repetition_across_contexts_and_counter_evidence() -> None:
    supporting = [
        signal(conversation="one", when=NOW - timedelta(days=2)),
        signal(conversation="two"),
    ]
    assert calculate_confidence(supporting, NOW) == 0.75
    assert calculate_confidence(supporting + [signal(relation="counter")], NOW) == 0.63


def test_old_evidence_is_discounted() -> None:
    old = signal(evidence_type="explicit_self_statement", when=NOW - timedelta(days=800))
    assert calculate_confidence([old], NOW) == 0.75
