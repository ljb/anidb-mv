from unittest import TestCase
from urllib.parse import parse_qs

from amv.file_info import FileInfo
from amv.network import messages


def _parse_mylistadd(message):
    decoded = message.decode("ascii")
    name, params_str = decoded.split(" ", maxsplit=1)

    return name, parse_qs(params_str)


class MylistaddMessageTest(TestCase):
    def test_watched_internal_file(self):
        file_info = FileInfo(
            size=1337,
            ed2k="abc123",
            watched=True,
            internal=True,
            view_date=1532983833.7,
            path="/tmp/test",
        )

        name, params = _parse_mylistadd(messages.mylistadd_message(file_info, "sess1"))
        self.assertEqual(name, "MYLISTADD")
        self.assertEqual(params["size"], ["1337"])
        self.assertEqual(params["ed2k"], ["abc123"])
        self.assertEqual(params["state"], ["1"])
        self.assertEqual(params["viewed"], ["1"])
        self.assertEqual(params["viewdate"], ["1532983833"])
        self.assertEqual(params["s"], ["sess1"])

    def test_not_watched_external_file(self):
        file_info = FileInfo(
            size=2000,
            ed2k="def456",
            watched=False,
            internal=False,
            view_date=1532983833.7,
            path="/tmp/test",
        )

        name, params = _parse_mylistadd(messages.mylistadd_message(file_info, "sess2"))

        self.assertEqual(params["state"], ["2"])
        self.assertEqual(params["viewed"], ["0"])
        self.assertNotIn("viewdate", params)
