"""
Smoke-tests the *installed* amv and amv-db, as opposed to the source tree that pytest
runs against. Install a build first (pipx install --force ., or pip install dist/*.whl
into a venv on PATH), then run this script with any Python 3.10 or later:

    python tests/smoke.py

Nothing here talks to AniDB. It checks that the entry points resolve, that the package
imports, and that the first things a new user runs into behave: help, usage errors, an
empty database and a missing config. pytest does not collect it, since it is not named
test_*.py, and it deliberately does not import amv -- the commands on PATH are the thing
under test.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class SmokeFailure(Exception):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def run(env: dict[str, str], *command: str) -> subprocess.CompletedProcess:
    return subprocess.run(command, env=env, capture_output=True, text=True, check=False)


def locate_commands() -> tuple[str, str]:
    amv = shutil.which("amv")
    amv_db = shutil.which("amv-db")
    check(amv is not None, "amv is not on PATH")
    check(amv_db is not None, "amv-db is not on PATH")
    check("/src/" not in amv, f"amv resolves to {amv}, which looks like the source tree")
    return amv, amv_db


def isolated_environment(home: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("XDG_")}
    env["HOME"] = str(home)
    return env


def check_help(env: dict[str, str]) -> None:
    result = run(env, "amv", "--help")
    check(result.returncode == 0, f"amv --help exited {result.returncode}")
    check("--replace" in result.stdout, "amv --help does not mention --replace")

    result = run(env, "amv-db", "--help")
    check(result.returncode == 0, f"amv-db --help exited {result.returncode}")
    check("retry" in result.stdout, "amv-db --help does not list retry")


def check_amv_db_without_subcommand(env: dict[str, str]) -> None:
    result = run(env, "amv-db")
    check(result.returncode == 2, f"amv-db without a subcommand exited {result.returncode}, expected 2")
    check(result.stderr.startswith("usage:"), "amv-db without a subcommand did not print usage on stderr")


def check_empty_database(env: dict[str, str], home: Path) -> None:
    result = run(env, "amv-db", "list")
    check(result.returncode == 0, f"amv-db list exited {result.returncode}")
    check(result.stdout == "", f"amv-db list printed something for an empty database: {result.stdout!r}")
    database = home / ".local" / "share" / "amv" / "amv.sqlite3"
    check(database.is_file(), "amv-db list did not create the database on the XDG path")


def check_missing_config(env: dict[str, str], home: Path) -> None:
    sample = home / "file.mkv"
    sample.write_text("sample\n")

    result = run(env, "amv", "-n", str(sample))
    check(result.returncode == 1, f"amv without a config exited {result.returncode}, expected 1")
    check("No config file exists" in result.stderr, "amv without a config did not explain itself on stderr")
    check(result.stdout == "", f"amv without a config wrote to stdout: {result.stdout!r}")
    check(sample.is_file(), "amv without a config moved or removed the file")


def main() -> int:
    try:
        amv, amv_db = locate_commands()
        print(f"Testing {amv} and {amv_db}")
        with tempfile.TemporaryDirectory() as home_name:
            home = Path(home_name)
            env = isolated_environment(home)
            check_help(env)
            check_amv_db_without_subcommand(env)
            check_empty_database(env, home)
            check_missing_config(env, home)
    except SmokeFailure as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
