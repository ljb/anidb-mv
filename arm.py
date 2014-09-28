#!/usr/bin/env python2.7

"""arm"""

import os
import optparse

from register import Register


class RegisterParser(optparse.OptionParser):
    """RegisterParser"""
    def __init__(self, usage="%prog [OPTION] FILES", version="%prog v0.01"):
        optparse.OptionParser.__init__(self, usage=usage, version=version)
        self.add_option("-b", "--burnt", action="store_const", const=2,
                        dest="state", default=1, help="mark file as burnt")
        self.add_option("-d", "--deleted", action="store_const", const=3,
                        dest="state", default=1, help="mark file as deleted")
        self.add_option("-r", "--remove", action="store_true", dest="remove",
                        help="remove entry from mylist")
    
    def parse_args(self, args=None, values=None):
        flags, fnames = optparse.OptionParser.parse_args(self, args, values)
        if not fnames:
            self.error("No arguments given")
        return flags, fnames


def main():
    """Main"""
    flags, fnames = RegisterParser().parse_args()
    register = Register()
    successes = []
    failures = []

    for fname in fnames:
        if flags.remove:
            response = register.remove(fname)
            print response
        else:
            response = register.register(fname, state=flags.state, edit=True)
            if response.rescode in ["210", "311"]:
                successes.append(fname)
            else:
                failures.append(fname)
    register.close()

    if successes:
        for fname in successes:
            print "Removing %s" % fname
            os.remove(fname)

    if failures:
        print "Files that failed to get registered:"
        for fname in failures:
            print fname

if __name__ == "__main__":
    main()
