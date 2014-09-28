#/usr/bin/env python

"""database"""

import sqlite3

#There is support for a local database in the anidb-library, but it requires
#a mysql-server which is overkill a complicates things for average users. This
#program instead uses sqlite3.
def get_db(db_filename):
    """Initiates the local database."""
    localdb = sqlite3.connect(db_filename)
    with localdb:
        localdb.execute("""CREATE TABLE IF NOT EXISTS files
            (filename TEXT, fid, size INTEGER, ed2k TEXT, state INTEGER,
            viewed INTEGER, viewdate INTEGER, registered INTEGER)""")
    return localdb
