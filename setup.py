#!/usr/bin/env python3

from distutils.core import setup

setup(name='anidb-mv',
      version='0.1',
      author='Jonas Bengtsson',
      description='Command line client for AniDB',
      author_email='jonas@bengtsson.cc',
      package_dir={'amv': 'amv'},
      packages=['amv', 'amv.network'],
      url='https://github.com/ljb/anidb-mv',
      scripts=['scripts/amv', 'scripts/amv-db'],
      license="GPLv3",
      long_description="""
        anidb-mv, or amv for short, is a command line client for AniDB.  It is
        similar to the standard mv command in Unix, but in addition to moving
        the files, it also tries to register them at AniDB.  If a file isn't
        found on AniDB, information about it is saved in a local database, and
        amv tries to register it the next time to command is used.
        """)
