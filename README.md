# AniDB-mv

AniDB-mv, or amv for short, is a command line client for AniDB. It is
similar to the standard mv command in Unix, but in addition to moving
the files, it also tries to register them at AniDB. If a file isn't
found at AniDB, information about it is saved in a local database.
Run `amv-db retry` later to attempt to register those files again, or
pass `-R`/`--retry-unregistered` to `amv` to retry them as part of the
next move.

The project consists of two commands: `amv` and `amv-db`. `amv` is the command
for moving files (or for registering them without moving them), and `amv-db`
is the command used for handling the files that failed to get registered.


### Prerequisites
Python 3.10+

### Installing
Install it with pip:
```
python -m pip install anidb-mv
```

This installs the required `pycryptodomex` dependency for ED2K hashing.

For an isolated CLI install, use `pipx`:
```
pipx install anidb-mv
```

Or install the local checkout:
```
python -m pip install .
```

To build a wheel and install the built package locally:
```
python -m pip install build
python -m build
python -m pip install --user dist/anidb_mv-*.whl
```

### Development
Set up a local development environment with:
```
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

Run the test suite with:
```
pytest -q
```

Run ruff with:
```
ruff check
ruff format --check
```

### Changelog

See [CHANGELOG.md](CHANGELOG.md). Note that 1.0.0 contains breaking changes if you
are coming from 0.1.

### Examples of Usage
* To move files and register them at AniDB: `amv file1.mkv file2.mkv /my/files/`

* To move a directory and register all files in it: `amv mydir /my/files`

* To register a file without moving it: `amv -n file.mkv`

* To list files that failed to get registered: `amv-db list`

* To clear files that failed to get registered: `amv-db clear`

* To retry registering files saved in the database: `amv-db retry`

* To retry registering during a move: `amv -R file1.mkv /my/files/`

* To replace a broken pre-release with the official release while keeping
  the original watch date: `amv-db replace /anime/broken.mkv /downloads/official.mkv`
