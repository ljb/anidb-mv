import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from .file_info import FileInfo


def _default_database_path() -> str:
    legacy_path = os.path.expanduser("~/.amv.sqlite3")
    if os.path.exists(legacy_path):
        return legacy_path
    xdg_data_home = os.getenv("XDG_DATA_HOME", "~/.local/share")
    return os.path.expanduser(os.path.join(xdg_data_home, "amv", "amv.sqlite3"))


@contextmanager
def open_database(database_path: str | None = None) -> Generator[sqlite3.Cursor]:
    if database_path is None:
        database_path = _default_database_path()
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
    connection = None
    try:
        connection = sqlite3.connect(database_path)
        # Workaround for https://github.com/ghaering/pysqlite/issues/109
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute(
            "create table if not exists unregistered_files ("
            "view_date datetime,"
            "watched boolean,"
            "internal boolean,"
            "ed2k varchar(32),"
            "size integer,"
            "path text"
            ")"
        )
        yield cursor
    finally:
        if connection:
            connection.commit()
            connection.close()


def clear(cursor: sqlite3.Cursor) -> None:
    cursor.execute("delete from unregistered_files")
    cursor.execute("vacuum")


def remove_files(cursor: sqlite3.Cursor, ids: list[int]) -> None:
    cursor.executemany("delete from unregistered_files where rowid=?", ((rowid,) for rowid in ids))


def get_unregistered_files(cursor: sqlite3.Cursor) -> list[FileInfo]:
    results = cursor.execute("select rowid, * from unregistered_files")
    return [
        FileInfo(
            id=result[0],
            view_date=result[1],
            watched=bool(result[2]),
            internal=bool(result[3]),
            ed2k=result[4],
            size=result[5],
            path=result[6],
        )
        for result in results
    ]


def add_unregistered_files(cursor: sqlite3.Cursor, file_infos: list[FileInfo]) -> None:
    cursor.executemany(
        "insert into unregistered_files values (?, ?, ?, ?, ? ,?)",
        (
            (file_info.view_date, file_info.watched, file_info.internal, file_info.ed2k, file_info.size, file_info.path)
            for file_info in file_infos
        ),
    )
