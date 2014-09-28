#!/usr/bin/env python

"""register"""

import os

from hashing import ed2k_of_path
from database import get_db

__import__("warnings").filterwarnings("ignore", category=DeprecationWarning)
from anidb.anidb import AniDBInterface

USERNAME = "RETRACTED"
PASSWORD = "RETRACTED"
DB_FILENAME = "/home/jonas/.jonasdb.sqlite3"


class Register:
    def __init__(self):
        self.anidb = None
        self.localdb = None

    def get_anidb(self):
        if not self.anidb:
            self.anidb = AniDBInterface()
            self.anidb.auth(USERNAME, PASSWORD)
        return self.anidb

    def get_localdb(self):
        if not self.localdb:
            self.localdb = get_db(DB_FILENAME)
        return self.localdb

    def remove(self, fname):
        ed2k = ed2k_of_path(fname)
        size = os.path.getsize(fname)
        return self.get_anidb().mylistdel(ed2k=ed2k, size=size)

    def register(self, fname, viewed=None, state=None, mtime=False,
                 edit=False):
        parameters = {"ed2k": ed2k_of_path(fname), "size": os.path.getsize(fname)}
        if viewed is not None:
            parameters["viewed"] = viewed
        if state is not None:
            parameters["state"] = state
        if mtime:
            parameters["viewdate"] = int(os.stat(fname).st_mtime)
            parameters["viewed"] = 1
        if edit:
            parameters["edit"] = 1
        else:
            if not state:
                parameters["state"] = 1
            if viewed is None:
                parameters["viewed"] = 1

        return self.get_anidb().mylistadd(**parameters)

    def close(self):
        if self.anidb:
            self.anidb.logout()
        if self.localdb:
            self.localdb.close()
