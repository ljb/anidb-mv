#!/usr/bin/env python2.7

"""amv"""

import os
import shutil

from register import Register
from aregister import RegisterParser


class MvParser(RegisterParser):
    """"Parse switches specific for amv"""
    def __init__(self, usage="%prog [OPTION] FILES DIR",
                 version="%prog v0.01"):
        RegisterParser.__init__(self, usage=usage, version=version)

    def parse_args(self, args=None, values=None):
        flags, fnames = RegisterParser.parse_args(self, args, values)
        if len(fnames) < 2:
            self.error("At least two arguments are required")
        elif not os.path.isdir(fnames[-1]):
            self.error("The last argument is not a directory")
        return flags, fnames[:-1], fnames[-1]


def register_file(fname, flags, register, successes, failures):
    """
    Register fname on register using the specified flags. Append it to the list
    successes if it was succesfull and to failures if it failed.
    """
    response = register.register(fname, flags.viewed, flags.state,
                                 flags.mtime, flags.edit)
    if response.rescode in ["210", "311"]:
        successes.append(fname)
    else:
        failures.append(fname)


def main():
    """Main function"""
    flags, args, dirname = MvParser().parse_args()
    register = Register()
    successes = []
    failures = []

    for arg in args:
        if os.path.isdir(arg):
            for dirpath, _, fnames in os.walk(arg):
                for fname in fnames:
                    path = os.path.join(dirpath, fname)
                    register_file(path, flags, register, successes, failures)
        else:
            register_file(arg, flags, register, successes, failures)
    register.close()

    if successes:
        print "Moving files that were registered"
        for fname in successes:
            print "%s -> %s" % (fname, dirname)
            shutil.move(fname, dirname)

    if failures:
        print "Files that failed to get registered:"
        for fname in failures:
            print fname

if __name__ == "__main__":
    main()
