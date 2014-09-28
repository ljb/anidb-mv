#!/usr/bin/env python

import sys

from hashing import ed2k_of_path

if len(sys.argv) < 2:
    print "No arguments given"
else:
    for fname in sys.argv[1:]:
        print "%s %s" % (fname, ed2k_of_path(fname))
