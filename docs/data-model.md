# Data model

Alembic revisions create the relational schema, memory-evidence links, claim history and trait keys, and an FTS5 event index. The initial schema is revision `bdc2ae95a5c2`:

- `datasets`, `source_files`, `people`, `person_aliases`, `conversations`, `events`
- `evidence`, `claims`, `claim_evidence`, `traits`, `memories`
- `corrections`, `distillation_runs`, `simulation_turns`

Revision `849c0df467ba` adds `memory_evidence`; `615206fdb353` adds claim history and trait keys; `749a0eb08f31` adds the FTS5 event index and triggers.
Revision `5b74b3c33ec2` adds persistent distillation jobs with progress, results, and sanitized failure status.

`events.event_id` is unique. `source_files` deduplicate SHA-256 hashes within a dataset. Every Evidence row requires a real Event and Person. A claim/evidence/relation tuple is unique. Dataset deletion cascades to its imported records. Claim and Trait rows are derived data; Event and Evidence retain the source trail. Corrections retain disputed or superseded claim history. Distillation runs record input and prompt hashes, and simulation turns retain their evidence trace. Migrations are the supported schema update path.
