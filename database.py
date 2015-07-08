import os
import sqlite3
from contextlib import contextmanager

@contextmanager
def open_database():
    connection = None
    try:
        connection = sqlite3.connect(os.path.expanduser('~/.amv.sqlite3'))
        cursor = connection.cursor()
        cursor.execute('create table if not exists episodes ('
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

def get_unregistered_files(cursor):
    results = cursor.execute('select * from episodes')
    return [{
        'view_date': result[0],
        'watched': bool(result[1]),
        'internal': bool(result[2]),
        'ed2k': result[3],
        'size': result[4],
        'path': result[5],
    } for result in results]

def add_unregistered_files(cursor, time, watched, internal, file_infos):
    cursor.executemany('insert into episodes values (?, ?, ?, ?, ? ,?)', [(
        time,
        int(watched),
        int(internal),
        file_info['ed2k'],
        file_info['size'],
        file_info['path']) for file_info in file_infos])
