#!/usr/bin/env python2.7

"""aregister"""

import os
import optparse

from register import Register

class RegisterParser(optparse.OptionParser):
    """RegisterParser"""
    def __init__(self, usage="%prog [OPTION] FILES", version="%prog v0.01"):
        optparse.OptionParser.__init__(self, usage=usage, version=version)
        self.add_option("-w", "--watched", action="store_const", dest="viewed",
                        const=1, help="mark file as watched")
        self.add_option("-W", "--not-watched", action="store_const", 
                        dest="viewed", const=0, 
                        help="don't mark file as watched")
        self.add_option("-e", "--edit", action="store_true", dest="edit",
                        default=False, help="edit entry if it exists")
        self.add_option("-i", "--internal", action="store_const", const=1,
                        dest="state", help="mark file as internally stored")
        self.add_option("-b", "--burnt", action="store_const", const=2,
                        dest="state", help="mark file as burnt")
        self.add_option("-m", "--mtime", action="store_true", dest="mtime",
                        default=False, help="use mtime of file as viewdate")
        self.add_option("-r", "--recursive", action="store_true",
                        dest="recursive", help="register files recursively")
    
    def parse_args(self, args=None, values=None):
        flags, fnames = optparse.OptionParser.parse_args(self, args, values)
        if not fnames:
            self.error("No arguments given")
        return flags, fnames

def register_fname(fname, flags, register, failures):
    response = register.register(fname, flags.viewed, flags.state,
                                 flags.mtime, flags.edit)
    if response.rescode not in ["210", "311"]:
        failures.append(fname)

def main():
    """Main"""
    flags, args = RegisterParser().parse_args()
    register = Register()
    failures = []

    for arg in args:
        if os.path.isdir(arg) and flags.recursive:
            for dirpath, dirnames, fnames in os.walk(args):
                for fname in fnames:
                    register_fname(fname, flags, register, failures)
        else:
            register_fname(arg, flags, register, failures)
    register.close()

    if failures:
        print "Files that failed to get registered:"
        for fname in failures:
            print fname

if __name__ == "__main__":
    main()
