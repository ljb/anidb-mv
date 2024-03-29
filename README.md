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
Python 3

### Installing
Install it with pip:
```
pip install anidb-mv
```

Or build and install manually:
```
pip install build
python -m build
pip install .
```

### Examples of Usage
* To move files and register them at AniDB: `amv file1.mkv file2.mkv /my/files/`

* To move a directory and register all files in it: `amv mydir /my/files`

* To register a file without moving it: `amv -n file.mkv`

* To list files that failed to get registered: `amv-db list`

* To clear files that failed to get registered: `amv-db clear`

### TODO
* Use XDG_CONFIG_HOME for database file
* Use alternative to hashlib for md4. The algoritm is deprecated in openssl.
