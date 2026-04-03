import tempfile
from unittest import TestCase
from unittest.mock import patch

from amv import hashing


class HashingTest(TestCase):
    def test_md4_digest(self):
        digest = hashing._md4_of_block(b"test").hexdigest()
        self.assertEqual("db346d691d7acc4dc2625db19f9e3f52", digest)

    def test_md4_uses_pycryptodomex_backend(self):
        hashlib_result = object()
        with patch("amv.hashing.MD4.new", return_value=hashlib_result) as md4_new:
            digest = hashing._md4_of_block(b"test")

        self.assertIs(hashlib_result, digest)
        md4_new.assert_called_once_with(b"test")

    def test_ed2k_digest_is_stable(self):
        with tempfile.NamedTemporaryFile() as file_:
            file_.write(b"test")
            file_.flush()

            digest = hashing.ed2k_of_path(file_.name)

        self.assertEqual(digest, "db346d691d7acc4dc2625db19f9e3f52")
