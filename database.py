import sqlite3
from contextlib import contextmanager

@contextmanager
def open_database():
    try:
        connection = sqlite3.connect('/home/jonas/.amv.sqlite3')
        cursor = connection.cursor()
        cursor.execute('create table if not exists episodes ('
                       'view_date datetime,'
                       'watched boolean,'
                       'internal boolean,'
                       'sha1 varchar(32),'
                       'size integer,'
                       'file_name text'
                       ')')
        yield cursor
    finally:
        connection.commit()
        connection.close()

def get_unregistered_files(cursor):
    results = cursor.execute('select * from episodes')
    return [{
        'view_date': result[0],
        'watched': result[1],
        'internal': result[2],
        'sha1': result[3],
        'size': result[4],
        'fname': result[5],
    } for result in results]

def add_unregistered_files(cursor, time, watched, internal, file_infos):
    cursor.executemany('insert into episodes values (?, ?, ?, ?, ? ,?)', [(
        time,
        int(watched),
        int(internal),
        file_info['sha1'],
        file_info['size'],
        file_info['fname']) for file_info in file_infos])
