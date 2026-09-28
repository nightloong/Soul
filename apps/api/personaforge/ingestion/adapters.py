"""Streaming source adapters for common text transcript formats."""

import csv
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

import ijson
from pydantic import ValidationError

from personaforge.domain.schemas import CanonicalEvent, SourceLocator


@dataclass(frozen=True)
class ImportIssue:
    locator: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class ImportRecord:
    event: CanonicalEvent | None = None
    issue: ImportIssue | None = None


class SourceAdapter(Protocol):
    source_type: str

    def probe(self, path: Path) -> bool: ...

    def preview(self, path: Path, dataset_id: str) -> Iterator[ImportRecord]: ...

    def convert(self, path: Path, dataset_id: str) -> Iterator[ImportRecord]: ...


def parse_timestamp(value: object) -> tuple[datetime | None, str | None]:
    if value is None or str(value).strip() == "":
        return None, "timestamp missing"
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}", str(value)):
        return None, "time of day has no date; preserved in context"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC), "timestamp has no timezone; assumed UTC"
        return parsed, None
    except ValueError:
        return None, f"invalid timestamp: {value}"


class BaseAdapter:
    source_type = "unknown"
    extensions: tuple[str, ...] = ()

    def probe(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def preview(self, path: Path, dataset_id: str) -> Iterator[ImportRecord]:
        yield from self.convert(path, dataset_id)

    def rows(self, path: Path) -> Iterator[tuple[str, dict | ImportIssue]]:
        raise NotImplementedError

    def convert(self, path: Path, dataset_id: str) -> Iterator[ImportRecord]:
        for locator, item in self.rows(path):
            if isinstance(item, ImportIssue):
                yield ImportRecord(issue=item)
                continue
            timestamp, warning = parse_timestamp(item.get("timestamp"))
            if warning:
                yield ImportRecord(issue=ImportIssue(locator, warning, "warning"))
            raw_name = str(item.get("speaker") or item.get("speaker_raw_name") or "").strip()
            if not raw_name:
                yield ImportRecord(issue=ImportIssue(locator, "speaker missing"))
                continue
            raw_text = item.get("text")
            if raw_text is None:
                yield ImportRecord(issue=ImportIssue(locator, "text missing"))
                continue
            try:
                context = {"channel": item.get("channel")} if item.get("channel") else {}
                raw_timestamp = str(item.get("timestamp") or "")
                if re.fullmatch(r"\d{2}:\d{2}:\d{2}", raw_timestamp):
                    context["time_of_day"] = raw_timestamp
                event = CanonicalEvent(
                    event_id=uuid5(NAMESPACE_URL, f"{dataset_id}:{path.name}:{locator}").hex,
                    dataset_id=dataset_id,
                    conversation_id=item.get("conversation_id"),
                    source=SourceLocator(type=self.source_type, file=path.name, locator=locator),
                    speaker_raw_name=raw_name,
                    timestamp=timestamp,
                    event_type=item.get("event_type") or "message",
                    text=str(raw_text),
                    context=context,
                )
            except ValidationError as exc:
                yield ImportRecord(issue=ImportIssue(locator, str(exc)))
                continue
            yield ImportRecord(event=event)


class GenericJSONLAdapter(BaseAdapter):
    source_type = "jsonl"
    extensions = (".jsonl",)

    def rows(self, path: Path) -> Iterator[tuple[str, dict | ImportIssue]]:
        with path.open(encoding="utf-8-sig") as source:
            for number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                locator = f"line:{number}"
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    yield locator, ImportIssue(locator, f"invalid JSON: {exc.msg}")
                    continue
                if not isinstance(payload, dict):
                    yield locator, ImportIssue(locator, "JSONL row must be an object")
                    continue
                yield locator, payload


class GenericJSONAdapter(BaseAdapter):
    source_type = "json"
    extensions = (".json",)

    def rows(self, path: Path) -> Iterator[tuple[str, dict | ImportIssue]]:
        with path.open("rb") as source:
            first = source.read(4096).lstrip()[:1]
            source.seek(0)
            prefix = "item" if first == b"[" else "messages.item" if first == b"{" else None
            if prefix is None:
                yield "root", ImportIssue("root", "JSON must be an array or object with messages")
                return
            count = 0
            try:
                for count, payload in enumerate(ijson.items(source, prefix), 1):
                    locator = f"item:{count}"
                    if isinstance(payload, dict):
                        yield locator, payload
                    else:
                        yield locator, ImportIssue(locator, "JSON message must be an object")
            except ijson.JSONError as exc:
                locator = f"item:{count + 1}"
                yield locator, ImportIssue(locator, f"invalid JSON: {exc}")
            if count == 0:
                yield "root", ImportIssue("root", "No messages found")


class CSVAdapter(BaseAdapter):
    source_type = "csv"
    extensions = (".csv",)

    def rows(self, path: Path) -> Iterator[tuple[str, dict | ImportIssue]]:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or not {"speaker", "text"} <= set(reader.fieldnames):
                yield "header", ImportIssue("header", "CSV requires speaker and text columns")
                return
            for row in reader:
                yield f"line:{reader.line_num}", row


TRANSCRIPT_LINE = re.compile(
    r"^(?:\[(?P<timestamp>[^]]+)\]\s*)?(?P<speaker>[^:：]+)[:：]\s*(?P<text>.*)$"
)


class PlainTranscriptAdapter(BaseAdapter):
    source_type = "transcript"
    extensions = (".txt",)

    def rows(self, path: Path) -> Iterator[tuple[str, dict | ImportIssue]]:
        with path.open(encoding="utf-8-sig") as source:
            for number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                locator = f"line:{number}"
                match = TRANSCRIPT_LINE.match(line.strip())
                if match is None:
                    yield locator, ImportIssue(locator, "unrecognized transcript line")
                else:
                    yield locator, match.groupdict()


class MarkdownTranscriptAdapter(PlainTranscriptAdapter):
    source_type = "markdown_transcript"
    extensions = (".md", ".markdown")

    def rows(self, path: Path) -> Iterator[tuple[str, dict | ImportIssue]]:
        with path.open(encoding="utf-8-sig") as source:
            for number, line in enumerate(source, 1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                stripped = re.sub(r"^[-*]\s+", "", stripped)
                stripped = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
                locator = f"line:{number}"
                match = TRANSCRIPT_LINE.match(stripped)
                if match is None:
                    yield locator, ImportIssue(locator, "unrecognized transcript line")
                else:
                    yield locator, match.groupdict()


ADAPTERS: tuple[BaseAdapter, ...] = (
    GenericJSONLAdapter(),
    GenericJSONAdapter(),
    CSVAdapter(),
    PlainTranscriptAdapter(),
    MarkdownTranscriptAdapter(),
)


def adapter_for(path: Path) -> BaseAdapter:
    for adapter in ADAPTERS:
        if adapter.probe(path):
            return adapter
    raise ValueError(f"Unsupported file type: {path.suffix}")
