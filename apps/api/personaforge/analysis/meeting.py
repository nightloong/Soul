"""Conservative, evidence-backed meeting analysis."""

import re
from collections import Counter
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from personaforge.db.models import Claim, ClaimEvidence, Conversation, Event, Evidence
from personaforge.distillation.merge import rebuild_persona


@dataclass(frozen=True)
class MeetingEvidence:
    event_id: str
    excerpt: str
    speaker: str
    source_file: str
    source_locator: str
    time_of_day: str | None


@dataclass(frozen=True)
class MeetingDecision:
    statement: str
    evidence: MeetingEvidence


@dataclass(frozen=True)
class MeetingActionItem:
    owner: str | None
    task: str
    deadline: str | None
    evidence: MeetingEvidence


def classify_utterance(text: str) -> list[str]:
    labels: list[str] = []
    if re.search(r"[?？]|要不要|能否|是否", text):
        labels.append("question")
    if re.search(r"建议|提议|可以先|先做|应该|不如", text):
        labels.append("proposal")
    if re.search(r"同意|支持|赞成", text):
        labels.append("support")
    if re.search(r"反对|不建议|先不要|担心|风险", text):
        labels.append("objection")
    if re.search(r"如果|前提|只要|除非|条件是", text):
        labels.append("condition")
    if re.search(r"决定|确定采用|最终采用|就按.+办|定了", text):
        labels.append("decision")
    if re.search(r"我来|负责|请.+处理|前完成|前提交", text):
        labels.append("action_item")
    return labels


def _evidence(event: Event) -> MeetingEvidence:
    return MeetingEvidence(
        event_id=event.event_id,
        excerpt=event.text or "",
        speaker=event.speaker_raw_name,
        source_file=event.source_file,
        source_locator=event.source_locator,
        time_of_day=event.context.get("time_of_day") if event.context else None,
    )


def analyze_meeting(session: Session, conversation_id: str) -> dict:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")
    events = list(
        session.scalars(
            select(Event)
            .where(Event.conversation_id == conversation_id)
            .order_by(Event.timestamp, Event.source_locator)
        )
    )
    distribution = Counter(event.speaker_raw_name for event in events)
    decisions: list[MeetingDecision] = []
    actions: list[MeetingActionItem] = []
    utterances = []
    for event in events:
        text = event.text or ""
        labels = classify_utterance(text)
        evidence = _evidence(event)
        utterances.append({"evidence": asdict(evidence), "labels": labels})
        if "decision" in labels:
            decisions.append(MeetingDecision(text, evidence))
        if "action_item" in labels:
            owner_match = re.search(r"([\w\u4e00-\u9fff]+)负责", text)
            owner = (
                event.speaker_raw_name
                if "我来" in text
                else owner_match.group(1)
                if owner_match
                else None
            )
            deadline_match = re.search(
                r"\d{4}-\d{2}-\d{2}|周[一二三四五六日天]前|明天前|今天前", text
            )
            actions.append(
                MeetingActionItem(
                    owner=owner,
                    task=text,
                    deadline=deadline_match.group(0) if deadline_match else None,
                    evidence=evidence,
                )
            )
    return {
        "id": conversation.id,
        "dataset_id": conversation.dataset_id,
        "title": conversation.title,
        "participants": sorted(distribution),
        "speaker_distribution": dict(distribution),
        "summary": (
            f"{len(events)} utterances, {len(distribution)} participants, "
            f"{len(decisions)} explicit decisions, {len(actions)} action items."
        ),
        "decisions": [asdict(item) for item in decisions],
        "action_items": [asdict(item) for item in actions],
        "utterances": utterances,
    }


def derive_decision_pattern(session: Session, person_id: str) -> Claim | None:
    """Create a long-term candidate only after matching behavior in two meetings."""
    events = list(
        session.scalars(
            select(Event)
            .where(Event.speaker_person_id == person_id, Event.conversation_id.is_not(None))
            .order_by(Event.timestamp, Event.source_locator)
        )
    )
    supporting = [
        event
        for event in events
        if event.text and re.search(r"先.{0,12}(验证|测试|原型)", event.text)
    ]
    if len({event.conversation_id for event in supporting}) < 2:
        return None
    existing = session.scalar(
        select(Claim).where(
            Claim.person_id == person_id,
            Claim.dimension == "decision_pattern",
            Claim.key == "scope_reduction_before_commit",
            Claim.status != "superseded",
        )
    )
    if existing is not None:
        return existing
    claim = Claim(
        person_id=person_id,
        dimension="decision_pattern",
        key="scope_reduction_before_commit",
        name="scope_reduction_before_commit",
        statement="在不确定性较高时倾向先进行小范围验证。",
        context={"channel": "meeting"},
        first_seen=min((event.timestamp for event in supporting if event.timestamp), default=None),
        last_seen=max((event.timestamp for event in supporting if event.timestamp), default=None),
    )
    session.add(claim)
    session.flush()
    for event in supporting:
        evidence = Evidence(
            source_event_id=event.event_id,
            person_id=person_id,
            excerpt=event.text,
            evidence_type="direct_behavior",
            reliability=0.75,
            observed_at=event.timestamp,
        )
        session.add(evidence)
        session.flush()
        session.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id, relation="support"))
    rebuild_persona(session, person_id)
    return claim
