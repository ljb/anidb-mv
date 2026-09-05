# AGENTS.md

Agent-facing notes for working in this repo. README has the user-facing overview.

## Environment

- Local venv lives at `./venv`. Activate before running anything: `source venv/bin/activate`.
- If `ruff` or `pytest` are missing, dev extras are not installed. Run `python -m pip install -e .[dev]`.
- Python 3.10+ (see `pyproject.toml`).

## Commands

- Tests: `pytest -q` (config in `pyproject.toml` sets `pythonpath = ["src"]`).
- Lint: `ruff check`
- Format check: `ruff format --check`
- CI runs all three on push and pull request (`.github/workflows/python-tests.yml`): pytest on
  Python 3.10 through 3.14, plus a lint job running `ruff check` and `ruff format --check`.
  Run them locally before declaring a task done rather than waiting for CI.
- `.github/workflows/publish.yml` publishes to PyPI via trusted publishing when a GitHub
  release is published.

## Project layout

- `src/amv/amv.py` — the `amv` CLI entry point.
- `src/amv/amv_db.py` — the `amv-db` CLI for inspecting/clearing the unregistered-files database.
- `src/amv/database.py` — sqlite3 access. Stores files that AniDB failed to register so they can be retried later.
- `src/amv/network/` — AniDB UDP client and protocol messages.
- `tests/` — pytest tests. `conftest.py` exposes `create_file_info()` for building `FileInfo` fixtures.

## Conventions

- User-facing output goes through `print`, not logging. Tests assert on `print` calls when they care about the output.
- `database` tests run against `sqlite3.connect(":memory:")` — do not mock sqlite. Mocking the DB layer is reserved for CLI/integration tests in `test_cli.py`.
- `test_cli.py` uses `patch(...).start()` in `setUp` with `addCleanup(patch.stopall)` rather than per-test decorators. Follow the existing pattern when adding tests there.
- Patches target `amv.amv.<name>` (the import site), not the source module. See commit 141e09b for rationale.
- The DB-retry flag is opt-in (`-r` / `--retry-unregistered`). Default behaviour is to print a one-line summary and skip the retry — keep that contract intact when touching `main()`.
