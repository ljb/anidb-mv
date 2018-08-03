import hashlib
import os


def _md4_of_block(block):
    return hashlib.new('md4', block)


def ed2k_of_path(path):
    block_size = 9500 * 1024
    digests = []

    with open(path, 'rb') as file_:
        if os.path.getsize(path) < block_size:
            digests.append(file_.read())
        else:
            while True:
                block = file_.read(block_size)
                digest = _md4_of_block(block).digest()
                digests.append(digest)
                if len(block) < block_size:
                    break
    return _md4_of_block(b''.join(digests)).hexdigest()
