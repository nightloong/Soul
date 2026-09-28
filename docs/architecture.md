# Architecture

The FastAPI backend in `apps/api/personaforge` owns ingestion, persistence, analysis, distillation, retrieval, simulation, and meeting analysis. The React frontend in `apps/web` uses `/api` routes and can be served locally through Vite preview. `personaforge.cli` exposes local administration and import commands.

Imports pass through format adapters into a canonical event, then a preview and SHA-256 confirmation gate before persistence. SQLite stores source files, events, people, evidence, claims, traits, memories, corrections, simulation turns, and distillation runs. Alembic owns schema changes. FTS5 indexes event text for local search.

Deterministic statistics and claim merging run locally. The model provider boundary uses an OpenAI-compatible HTTP endpoint for structured extraction and simulation. It validates extracted event references and quoted text against the stored source before creating evidence. The runtime selects traits, memories, and related events, then saves a trace of what it supplied to the model. Meeting analysis separates per-meeting decisions and actions from patterns requiring multiple meetings.

The domain, ingestion, analysis, retrieval, and merge services do not depend on the web UI. Tests use synthetic conversations and model doubles.
