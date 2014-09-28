#!/usr/bin/env python

"""hashing"""

# multihash doesn't seem to work on my 64 bit system. It is probably
# preferable to use a library if one that is working exists. 

import os
import hashlib

# md4 might not be supported on all systems
def md4_of_block(block):
    """Returns the md4-hash of a block"""
    return hashlib.new('md4', block)

# This function requires 9500 KiB of memory and is quite slow.
def ed2k_of_path(path):
    """Returns a ed2k-hash given a path"""
    blocksize = 9500 * 1024
    digests = []

    with open(path, 'rb') as fobj:
        if os.path.getsize(path) < blocksize:
            digests.append(fobj.read())
        else:
            while True:
                block = fobj.read(blocksize)
                digest = md4_of_block(block).digest()
                digests.append(digest)
                if len(block) < blocksize:
                    break
    return md4_of_block(''.join(digests)).hexdigest()
