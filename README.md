# PersonaForge

[English](./README.md) | [简体中文](./README.zh-CN.md)

PersonaForge is a local-first, evidence-backed persona research application. It imports conversations, tracks the source of each inferred claim, supports corrections, retrieves relevant evidence, and runs clearly labelled persona simulations. The repository implements Phases 0–12 of the accompanying execution plan.

## Run locally

Requires Python 3.11+, Node.js 22+, and SQLite with FTS5. The examples below use the virtual environment's Python on Unix. On Windows replace `.venv/bin/python` with `.venv\Scripts\python.exe`.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
npm ci
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn personaforge.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
npm run build
npm run preview
```

Open the URL printed by Vite, usually `http://127.0.0.1:4173`. The built frontend proxies `/api` to the local backend. On this Windows workspace, Vite's development dependency optimizer fails when launched from a path containing Chinese characters; build plus preview is the verified local workflow.

## First import

The UI supports datasets, people, previewing and applying an import, search, evidence and claim review, corrections, distillation, simulation, and meeting analysis. The synthetic examples in `examples/` are safe to experiment with. JSON, JSONL, CSV, TXT, and Markdown are accepted. An import preview reports unresolved speakers and a SHA-256 hash; applying it requires the hash and an explicit mapping. Reimporting the same source is idempotent.

The CLI is available through `.venv/bin/python -m personaforge.cli --help`. For example:

```bash
.venv/bin/python -m personaforge.cli dataset create "Demo"
.venv/bin/python -m personaforge.cli person create "Ava" --dataset DATASET_ID
.venv/bin/python -m personaforge.cli import preview examples/synthetic-chat/project.jsonl
```

Use the hash and raw speaker names returned by preview when applying the import. See `.venv/bin/python -m personaforge.cli import apply --help` for the exact flags.

## Model connection

Set `PERSONAFORGE_MODEL_BASE_URL`, `PERSONAFORGE_MODEL_NAME`, and `PERSONAFORGE_MODEL_API_KEY` in the backend process environment for an OpenAI-compatible endpoint; `.env.example` lists the names and a local endpoint example. On PowerShell, use `$env:PERSONAFORGE_MODEL_NAME='model-name'` and equivalent assignments before starting Uvicorn. Import, statistics, search, corrections, and claim rebuilding work without a model. Distillation and persona simulation call the configured model. The API key is read from the environment and is not stored in SQLite.

Distillation runs as a background job. The persona page polls its saved progress and offers retry after failure. The same status is available at `GET /api/distillation/jobs/{id}`; failures expose only an exception type, not the model error body.

## Verification

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m alembic check
npm run lint
npm test
npm run build
```

Browser coverage uses Microsoft Edge on Windows. Start the API on port 8000 and `npm run preview -- --port 5173` in separate terminals, then run `PERSONAFORGE_E2E_EXTERNAL=1 npx playwright test` (set the environment variable with PowerShell syntax on Windows). The built-in Playwright web server can be used where it starts and stops reliably.

## Privacy and provenance

Private source material belongs in `data/private/`, which Git ignores along with `.env` and SQLite databases. An external model endpoint receives selected event excerpts during distillation or simulation; use a local endpoint to keep that processing on the device. Each claim, memory, simulation trace, and meeting finding retains evidence references. Simulation output is explicitly labelled as a simulation, never as the person's actual words.

Architecture, data model, privacy details, prompt boundaries, and phase reports are in `docs/`.
The synthetic 100,000-event benchmark is available as `.venv/bin/python scripts/benchmark_100k.py` (use the Windows virtual-environment path on Windows).

## Dependencies and licenses

Python runtime: FastAPI (MIT), Uvicorn (BSD-3-Clause), Pydantic (MIT), SQLAlchemy (MIT), Alembic (MIT), python-multipart (Apache-2.0), ijson (BSD-3-Clause), and httpx (BSD-3-Clause). Frontend: React, React DOM, React Router, Vite, ESLint, Vitest, Testing Library, and jsdom (MIT); TypeScript and Playwright (Apache-2.0). `package-lock.json` records exact JavaScript versions. Each dependency's own license text is authoritative.
