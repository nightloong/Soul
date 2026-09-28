# Canonical event schema

`CanonicalEvent` in `personaforge.domain.schemas` is the adapter contract. It includes a stable event ID, dataset and optional conversation IDs, a `SourceLocator` (`type`, `file`, `locator`), raw speaker and optional mapped person, optional timestamp, event type, text, optional reply target, context, and metadata.

JSON, JSONL, CSV, TXT, and Markdown adapters populate this contract. Streaming parsing avoids loading large JSON and JSONL sources into memory. If a speaker cannot be mapped confidently, `speaker_person_id` remains null and the preview reports it. Incomplete timestamps remain explicitly unknown; adapters may preserve a time-only value in context without inventing a date.
