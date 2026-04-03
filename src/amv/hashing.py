import os

from Cryptodome.Hash import MD4


def _md4_of_block(block: bytes) -> MD4.MD4Hash:
    return MD4.new(block)


def ed2k_of_path(path: str) -> str:
    block_size = 9500 * 1024
    digests = []

    with open(path, 'rb') as file_:
        if os.path.getsize(path) < block_size:
            digests.append(file_.read())
        else:
            while block := file_.read(block_size):
                digests.append(_md4_of_block(block).digest())
    return _md4_of_block(b''.join(digests)).hexdigest()
