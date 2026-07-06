# AI Content Factory

Automated faceless YouTube video creation from Reddit stories. Cross-platform
PySide6 desktop application.

## Status

Phase 1 (Foundation) — application skeleton, config, database, plugin registry,
GUI shell with Dashboard. See
`docs/superpowers/specs/2026-07-06-ai-content-factory-design.md` for the full
architecture and `docs/superpowers/plans/` for per-phase plans.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest             # run tests
.venv/bin/python main.py     # launch the app
```

User data lives under `~/.aicf/` (override with `$AICF_HOME` for tests).
