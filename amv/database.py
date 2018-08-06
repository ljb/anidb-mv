import os
import sqlite3
from contextlib import contextmanager


@contextmanager
def open_database(database_path=None):
    database_path = database_path or os.path.expanduser('~/.amv.sqlite3')
    connection = None
    try:
        connection = sqlite3.connect(database_path)
        # Workaround for https://github.com/ghaering/pysqlite/issues/109
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute('create table if not exists unregistered_files ('
                       'view_date datetime,'
                       'watched boolean,'
                       'internal boolean,'
                       'ed2k varchar(32),'
                       'size integer,'
                       'path text'
                       ')')
        yield cursor
    finally:
        if connection:
            connection.commit()
            connection.close()


def clear(cursor):
    cursor.execute('delete from unregistered_files')
    cursor.execute('vacuum')


def remove_files(cursor, ids):
    cursor.executemany('delete from unregistered_files where rowid=?', ((rowid,) for rowid in ids))


def get_unregistered_files(cursor):
    results = cursor.execute('select rowid, * from unregistered_files')
    return [{
        'id': result[0],
        'view_date': result[1],
        'watched': bool(result[2]),
        'internal': bool(result[3]),
        'ed2k': result[4],
        'size': result[5],
        'path': result[6],
    } for result in results]


def add_unregistered_files(cursor, file_infos):
    cursor.executemany('insert into unregistered_files values (?, ?, ?, ?, ? ,?)', ((
        file_info['view_date'],
        file_info['watched'],
        file_info['internal'],
        file_info['ed2k'],
        file_info['size'],
        file_info['path']) for file_info in file_infos))
