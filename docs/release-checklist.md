# v0.1.0 release checklist

- [x] Python tests and Ruff pass locally.
- [x] Frontend lint, tests, and production build pass locally.
- [x] Alembic upgrade and schema drift check pass locally.
- [x] Synthetic import and browser flow pass locally.
- [x] Synthetic 100,000-event import and FTS5 query measured locally.
- [x] `.env`, API credentials, databases, and `data/private/` are Git ignored; local source scan found no credential patterns. CI includes gitleaks.
- [ ] Fresh Git clone, clean install, and CI run against a remote repository.
- [ ] Create and publish GitHub release `v0.1.0` after the destination repository is configured and approved.

The last two items need a Git remote; none is configured in this workspace. No real conversations are part of the release candidate.
