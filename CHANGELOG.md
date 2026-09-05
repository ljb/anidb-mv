# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-06

The previous release on PyPI is 0.1. Versions 0.2.0 and 0.3.0 were tagged in the
repository and built locally but never published, so this entry covers everything
since 0.1.

### Upgrading from 0.1

- Python 3.10 or later is now required.
- `amv` no longer retries the files in the database on every run. It prints a
  one-line summary instead; pass `-R`/`--retry-unregistered` to get the old
  behaviour. `--no-db-report` is gone.
- Replace `-W`/`--not-watched` with `-u`/`--unwatched`.
- `amv-db` now requires a subcommand instead of doing nothing.
- Scripts that parse `amv`'s output should note that error messages moved to
  stderr.
- The config file and the database moved to XDG directories, but the old
  locations still work — see below. Nothing has to be moved by hand.

### Added

- `amv-db retry`, which re-registers the files in the database without moving
  anything.
- `amv-db replace`, which swaps a file in the database for a new release while
  keeping the original watch date and flags.
- `-R`/`--retry-unregistered` on `amv`, the opt-in replacement for the old
  always-on behaviour.
- Short options for every `amv` flag: `-u` for `--unwatched` and `-e` for
  `--external` were previously long-only.
- `amv-db --help` documents every subcommand. Only `replace` used to have any
  help text.
- `-v` is accepted both before and after an `amv-db` subcommand.
- A test suite of 59 tests, GitHub Actions running it on Python 3.10 through
  3.14, and a lint job.

### Changed

- **`-W`/`--not-watched` is now `-u`/`--unwatched`**, stating what it does rather
  than what it negates.
- **The database is no longer retried by default.** Unregistered files are
  reported as a one-line summary, each file listed, and retried only on request.
- **Error messages go to stderr.** Everything went to stdout, so redirecting
  `amv`'s output to a file swallowed the reason a run failed and left the
  terminal blank.
- **`amv-db` with no subcommand exits 2 with usage** instead of printing nothing
  and exiting 0.
- **The config file is read from `$XDG_CONFIG_HOME/amv/config`**, falling back to
  `~/.amvrc` if that exists.
- **The database lives in `$XDG_DATA_HOME/amv/amv.sqlite3`**, unless
  `~/.amv.sqlite3` already exists, in which case it keeps being used.
- ED2K hashing uses pycryptodomex instead of `hashlib.new("md4")`, which modern
  OpenSSL builds no longer provide. This adds a dependency but is what makes the
  program run at all on a current system.
- The package moved to a `src/` layout with console-script entry points declared
  in `pyproject.toml`, replacing `setup.py` and the `scripts/` directory.
- The license is declared as the SPDX expression `GPL-3.0-or-later` rather than
  the free-text "GPLv3".
- `FileInfo` is a frozen dataclass rather than a dict, and the code carries type
  hints throughout.

### Fixed

- **`--not-watched` and `--external` did nothing.** Both values were collected
  and then dropped: the MYLISTADD message never included the watched, internal
  or viewdate fields, so every file was registered with AniDB's defaults
  regardless of the flags. Present in 0.1.
- **`amv` could hang forever.** If the worker thread raised an unexpected
  exception the queue sentinel was never sent, and registration blocked
  indefinitely.
- A socket leak and missing timeout handling in the UDP client. A registration
  that got no response used to wait forever; it now reports the timeout and
  moves on.
- Files that had been registered successfully were not always removed from the
  database, because `FileInfo` equality included the database id.
- The sdist shipped `tests/test_*.py` without `tests/conftest.py`, so four of the
  seven test files could not even be imported from it.
- `ruff check` and `ruff format --check` were failing on the default branch.
- A missing space in the outdated-protocol warning, which read
  "…UDP protocol.Please download…".

### Removed

- `--no-db-report`, replaced by the inverted `-R`/`--retry-unregistered`.
- Support for Python versions before 3.10.

## [0.1] - 2018-08-12

First release on PyPI.

[1.0.0]: https://github.com/ljb/anidb-mv/compare/v0.1...v1.0.0
[0.1]: https://github.com/ljb/anidb-mv/releases/tag/v0.1
