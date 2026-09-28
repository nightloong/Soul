from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from personaforge.analysis.statistics import analyze_person


@dataclass
class Message:
    event_id: str
    conversation_id: str
    speaker_person_id: str
    timestamp: datetime
    text: str


def at(hour: int, minute: int = 0, day: int = 1) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def test_statistics_are_observable_features() -> None:
    messages = [
        Message("1", "a", "bob", at(9), "开始"),
        Message("2", "a", "alice", at(9, 2), "先测试！😊"),
        Message("3", "a", "alice", at(9, 3), "先测试？"),
        Message("4", "a", "bob", at(9, 4), "好"),
        Message("5", "a", "alice", at(9, 5), "先测试！"),
    ]
    result = analyze_person(messages, "alice")
    assert result.kind == "derived_statistical_feature"
    assert result.message_count == 3
    assert result.burst_max == 2
    assert result.reply_delay_median_seconds == 90
    assert result.emoji_count == 1
    assert result.question_ratio == 1 / 3
    assert ("先测试", 3) in result.common_phrases
    assert result.active_hours == {9: 3}
    assert "cold" not in str(result.to_dict())


def test_reply_gap_excludes_next_day() -> None:
    messages = [
        Message("1", "a", "bob", at(9), "问题"),
        Message("2", "a", "alice", at(9, day=2), "回答"),
    ]
    result = analyze_person(messages, "alice", max_reply_gap=timedelta(hours=12))
    assert result.reply_sample_count == 0
    assert result.reply_delay_median_seconds is None


def test_empty_person_is_safe() -> None:
    result = analyze_person([], "missing")
    assert result.message_count == 0
    assert result.length_p90 == 0
    assert result.short_reply_ratio == 0
