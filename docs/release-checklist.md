# v0.1.0 release checklist

- [x] Python tests and Ruff pass locally.
- [x] Frontend lint, tests, and production build pass locally.
- [x] Alembic upgrade and schema drift check pass locally.
- [x] Synthetic import and browser flow pass locally.
- [x] Synthetic 100,000-event import and FTS5 query measured locally.
- [x] Local Git clone, clean dependency installation, Python tests, migration, frontend lint/tests/build pass.
- [x] npm audit reports zero vulnerabilities after updating Vitest to 4.1.11.
- [x] `.env`, API credentials, databases, and `data/private/` are Git ignored; local source scan found no credential patterns. CI includes gitleaks.
- [ ] CI run against a remote repository.
- [ ] Create and publish GitHub release `v0.1.0` after the destination repository is configured and approved.

The last two items need a Git remote; none is configured in this workspace. The local clean clone used a Python virtual environment with access to the bundled runtime packages and installed missing dependencies through pip. No real conversations are part of the release candidate.
