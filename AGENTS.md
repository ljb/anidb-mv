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
- Smoke test of the installed package: `python tests/smoke.py` (needs a built `amv` on PATH, e.g.
  `pipx install --force .`). It never talks to AniDB. Run it when touching packaging,
  `pyproject.toml`, `MANIFEST.in` or the entry points -- pytest runs against `src/` and
  cannot see whether the built package installs and starts.
- CI runs all of these on push and pull request (`.github/workflows/python-tests.yml`): pytest on
  Python 3.10 through 3.14, a lint job running `ruff check` and `ruff format --check`, and a
  build job that builds the package, runs `twine check`, checks the sdist contents and runs
  `tests/smoke.py` against the wheel installed in a clean venv.
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
- Patches target the import site, not the module a name is defined in. For code under test in
  `amv.amv` that is `amv.amv.<name>`; `amv_db` does `from .amv import read_config`, so its tests
  must patch `amv.amv_db.read_config`. Getting this wrong is not loud -- the real function simply
  runs. See 141e09b for the rationale and a89c7ed for what it costs to get it wrong.
- The DB-retry flag is opt-in (`-R` / `--retry-unregistered`). Default behaviour is to print a one-line summary and skip the retry — keep that contract intact when touching `main()`.

## Changelog

`CHANGELOG.md` documents each release against the previous one on PyPI, not against the previous
tag -- several versions were tagged here and never published.

Bold marks entries where a change to existing behaviour is the point, so an upgrader can scan for
what will bite them:

- **Removed, Changed, Fixed**: bold the first sentence of entries a user of the command notices.
  Leave plain the ones about packaging, internals or the Python API -- the src layout, the SPDX
  licence field, a dataclass replacing a dict, a test-only fix.
- **Added**: no bold. Everything in it is new by definition, so emphasis marks nothing.
- The bolded sentence states the effect; the explanation follows in plain text.

When you change user-visible behaviour, add the entry in the same commit. The date under the
version heading is the release date -- set it when you cut the release, not when you write the entry.
