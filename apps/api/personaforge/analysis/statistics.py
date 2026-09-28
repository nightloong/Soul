"""Observable communication statistics. These are not personality claims."""

import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Protocol

MAX_REPLY_GAP = timedelta(hours=12)
PUNCTUATION = ("。", "！", "？", "…", "～", "!!", "??")
EMOJI = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]")
TOKENS = re.compile(r"[A-Za-z]+|[\u4e00-\u9fff]")
DEFAULT_STOP_WORDS = frozenset({"的", "了", "是", "在", "我", "你", "他", "她", "们"})


class StatisticalEvent(Protocol):
    event_id: str
    conversation_id: str | None
    speaker_person_id: str | None
    timestamp: datetime | None
    text: str | None


@dataclass
class StatisticalFeatures:
    kind: str
    person_id: str
    message_count: int
    length_mean: float
    length_median: float
    length_p90: float
    burst_mean: float
    burst_max: int
    punctuation: dict[str, int]
    emoji_count: int
    single_line_count: int
    multi_line_count: int
    paragraph_count: int
    common_phrases: list[tuple[str, int]]
    reply_delay_median_seconds: float | None
    reply_sample_count: int
    active_hours: dict[int, int]
    active_weekdays: dict[int, int]
    question_ratio: float
    short_reply_ratio: float

    def to_dict(self) -> dict:
        return asdict(self)


def percentile(values: list[int], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percent
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower))


def analyze_person(
    events: Iterable[StatisticalEvent],
    person_id: str,
    *,
    min_phrase_frequency: int = 2,
    stop_words: frozenset[str] = DEFAULT_STOP_WORDS,
    max_reply_gap: timedelta = MAX_REPLY_GAP,
) -> StatisticalFeatures:
    all_events = list(events)
    own = [event for event in all_events if event.speaker_person_id == person_id and event.text]
    texts = [event.text or "" for event in own]
    lengths = [len(text.strip()) for text in texts]
    punctuation = {mark: sum(text.count(mark) for text in texts) for mark in PUNCTUATION}
    hours: Counter[int] = Counter()
    weekdays: Counter[int] = Counter()
    for event in own:
        if event.timestamp is not None:
            hours[event.timestamp.hour] += 1
            weekdays[event.timestamp.weekday()] += 1

    phrases: Counter[str] = Counter()
    for text in texts:
        tokens = TOKENS.findall(text.lower())
        for size in (2, 3):
            for index in range(len(tokens) - size + 1):
                phrase_tokens = tokens[index : index + size]
                if any(token in stop_words for token in phrase_tokens):
                    continue
                phrases["".join(phrase_tokens)] += 1
    common = sorted(
        ((phrase, count) for phrase, count in phrases.items() if count >= min_phrase_frequency),
        key=lambda item: (-item[1], item[0]),
    )[:20]

    grouped: dict[str, list[StatisticalEvent]] = defaultdict(list)
    for event in all_events:
        if event.timestamp is not None and event.conversation_id is not None:
            grouped[event.conversation_id].append(event)
    bursts: list[int] = []
    reply_delays: list[float] = []
    for conversation in grouped.values():
        conversation.sort(key=lambda event: event.timestamp or datetime.min)
        current_burst = 0
        previous: StatisticalEvent | None = None
        for event in conversation:
            if event.speaker_person_id == person_id:
                current_burst = (
                    current_burst + 1 if previous and previous.speaker_person_id == person_id else 1
                )
                if previous and previous.speaker_person_id != person_id and previous.timestamp:
                    delay = event.timestamp - previous.timestamp  # type: ignore[operator]
                    if timedelta(0) <= delay <= max_reply_gap:
                        reply_delays.append(delay.total_seconds())
            elif current_burst:
                bursts.append(current_burst)
                current_burst = 0
            previous = event
        if current_burst:
            bursts.append(current_burst)

    count = len(texts)
    return StatisticalFeatures(
        kind="derived_statistical_feature",
        person_id=person_id,
        message_count=count,
        length_mean=statistics.mean(lengths) if lengths else 0.0,
        length_median=statistics.median(lengths) if lengths else 0.0,
        length_p90=percentile(lengths, 0.9),
        burst_mean=statistics.mean(bursts) if bursts else 0.0,
        burst_max=max(bursts, default=0),
        punctuation=punctuation,
        emoji_count=sum(len(EMOJI.findall(text)) for text in texts),
        single_line_count=sum("\n" not in text for text in texts),
        multi_line_count=sum("\n" in text for text in texts),
        paragraph_count=sum("\n\n" in text for text in texts),
        common_phrases=common,
        reply_delay_median_seconds=statistics.median(reply_delays) if reply_delays else None,
        reply_sample_count=len(reply_delays),
        active_hours=dict(sorted(hours.items())),
        active_weekdays=dict(sorted(weekdays.items())),
        question_ratio=sum("?" in text or "？" in text for text in texts) / count if count else 0.0,
        short_reply_ratio=sum(len(text.strip()) <= 4 for text in texts) / count if count else 0.0,
    )
