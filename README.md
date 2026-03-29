# AniDB-mv

AniDB-mv, or amv for short, is a command line client for AniDB. It is
similar to the standard mv command in Unix, but in addition to moving
the files, it also tries to register them at AniDB. If a file isn't
found on AniDB, information about it is saved in a local database, and
amv tries to register it the next time to command is used.

The project consists of two commands: amv and amv-db. amv is the command
for moving files (or for registering them without moving them), and amv-db
is the command used for handling the files that failed to get registered.


### Prerequisites
Python 3.8+

### Installing
Install it with pip:
```
python -m pip install anidb-mv
```

This installs the required `pycryptodomex` dependency for ED2K hashing.

For an isolated CLI install, use pipx:
```
pipx install anidb-mv
```

Or install the local checkout:
```
python -m pip install .
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

Run pylint with:
```
pylint --rcfile=pylintrc src/amv
```

### Examples of Usage
* To move files and register them at AniDB: `amv file1.mkv file2.mkv /my/files/`

* To move a directory and register all files in it: `amv mydir /my/files`

* To register a file without moving it: `amv -n file.mkv`

* To list files that failed to get registered: `amv-db list`

* To clear files that failed to get registered: `amv-db clear`

### TODO
* Use XDG_CONFIG_HOME for database file
