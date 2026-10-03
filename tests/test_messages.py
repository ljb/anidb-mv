from unittest import TestCase
from urllib.parse import parse_qs

from amv.exceptions import AnidbProtocolException
from amv.file_info import FileInfo
from amv.network import messages


def _parse_command(message):
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

        name, params = _parse_command(messages.mylistadd_message(file_info, "sess1"))
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

        name, params = _parse_command(messages.mylistadd_message(file_info, "sess2"))

        self.assertEqual(params["state"], ["2"])
        self.assertEqual(params["viewed"], ["0"])
        self.assertNotIn("viewdate", params)


class MylistaddEditTest(TestCase):
    def test_edit_is_added_on_request(self):
        file_info = FileInfo(path="x", size=1, ed2k="a" * 32, watched=True, internal=True, view_date=5.0)

        _, plain = _parse_command(messages.mylistadd_message(file_info, "sess"))
        _, edit = _parse_command(messages.mylistadd_message(file_info, "sess", edit=True))

        self.assertNotIn("edit", plain)
        self.assertEqual(["1"], edit["edit"])
        self.assertEqual(plain, {k: v for k, v in edit.items() if k != "edit"})


class MylistMessagesTest(TestCase):
    def test_mylist_message(self):
        name, params = _parse_command(messages.mylist_message(1337, "a" * 32, "sess"))

        self.assertEqual("MYLIST", name)
        self.assertEqual({"size": ["1337"], "ed2k": ["a" * 32], "s": ["sess"]}, params)

    def test_mylistdel_message(self):
        name, params = _parse_command(messages.mylistdel_message(1337, "a" * 32, "sess"))

        self.assertEqual("MYLISTDEL", name)
        self.assertEqual({"size": ["1337"], "ed2k": ["a" * 32], "s": ["sess"]}, params)


class ParseMessageTest(TestCase):
    def test_status_line_only(self):
        parsed = messages.parse_message(b"210 MYLIST ENTRY ADDED\n")

        self.assertEqual({"number": 210, "string": "MYLIST ENTRY ADDED"}, parsed)

    def test_login_reply_carries_the_session(self):
        self.assertEqual(
            {"number": 200, "session": "abc", "string": "LOGIN ACCEPTED"},
            messages.parse_message(b"200 abc LOGIN ACCEPTED"),
        )

    def test_data_lines_are_kept_separately(self):
        parsed = messages.parse_message(b"221 MYLIST\n1|2|3|4|5|6|1|0|||\n")

        self.assertEqual({"number": 221, "string": "MYLIST", "data": "1|2|3|4|5|6|1|0|||"}, parsed)

    def test_unparseable_message(self):
        with self.assertRaises(AnidbProtocolException):
            messages.parse_message(b"garbage")


class ParseMylistEntryTest(TestCase):
    def test_watched_internal_entry(self):
        entry = messages.parse_mylist_entry("271938|2660|40|12|1|1532983833|1|1532983833|||")

        self.assertEqual(271938, entry.lid)
        self.assertTrue(entry.watched)
        self.assertTrue(entry.internal)
        self.assertEqual(1532983833.0, entry.view_date)

    def test_unwatched_external_entry(self):
        entry = messages.parse_mylist_entry("271938|2660|40|12|1|1532983833|2|0|||")

        self.assertFalse(entry.watched)
        self.assertFalse(entry.internal)
        self.assertEqual(0.0, entry.view_date)

    def test_only_cd_dvd_storage_counts_as_external(self):
        for state in (0, 1, 3, 4):
            with self.subTest(state=state):
                self.assertTrue(messages.parse_mylist_entry(f"1|2|3|4|5|6|{state}|0|||").internal)

    def test_too_few_fields(self):
        with self.assertRaises(AnidbProtocolException):
            messages.parse_mylist_entry("1|2|3")


class RedactTest(TestCase):
    def test_password_is_hidden_in_auth_message(self):
        rendered = messages.redact(messages.auth_message("user", "s3cret&pass"))

        self.assertNotIn("s3cret", rendered)
        self.assertIn("pass=***", rendered)
        self.assertIn("user=user", rendered)
        self.assertIn("protover=", rendered)

    def test_other_messages_are_rendered_as_is(self):
        datagram = messages.mylist_message(1337, "a" * 32, "sess")

        self.assertEqual(str(datagram), messages.redact(datagram))
