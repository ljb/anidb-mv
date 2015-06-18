#!/usr/bin/env python

import os
import hashlib

def _md4_of_block(block):
    return hashlib.new('md4', block)

def ed2k_of_path(path):
    blocksize = 9500 * 1024
    digests = []

    with open(path, 'rb') as fobj:
        if os.path.getsize(path) < blocksize:
            digests.append(fobj.read())
        else:
            while True:
                block = fobj.read(blocksize)
                digest = _md4_of_block(block).digest()
                digests.append(digest)
                if len(block) < blocksize:
                    break
    return _md4_of_block(b''.join(digests)).hexdigest()
