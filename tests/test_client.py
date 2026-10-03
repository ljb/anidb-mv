import socket
from queue import Queue
from threading import Event
from unittest import TestCase
from unittest.mock import MagicMock, patch

from conftest import create_file_info

from amv.exceptions import AnidbProtocolException
from amv.network.client import UdpClient
from amv.network.messages import MylistEntry


class UdpClientTest(TestCase):
    def setUp(self):
        self.shutdown_event = Event()
        self.queue = Queue()
        self.config = {"username": "user", "password": "pass", "local_port": 9000}
        self.socket_mock = MagicMock()
        self.socket_patch = patch("amv.network.client.socket.socket", return_value=self.socket_mock)
        self.time_patch = patch("amv.network.client.time")
        self.socket_patch.start()
        self.time_mock = self.time_patch.start()
        self.time_mock.time.return_value = 0
        self.time_mock.sleep = MagicMock()
        self.addCleanup(patch.stopall)

    def _login_response(self):
        return (b"200 abc123 LOGIN ACCEPTED", None)

    def _enter_client(self):
        self.socket_mock.recvfrom.return_value = self._login_response()
        client = UdpClient(self.shutdown_event, False, self.config, self.queue)
        client.__enter__()

        return client

    def test_register_file_successfully(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"210 MYLIST ENTRY ADDED", None)
        self.queue.put(create_file_info("/tmp/file1"))
        self.queue.put(None)

        result = client.register_file_infos()

        self.assertEqual(result, [])

    def test_register_file_already_registered(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"310 FILE ALREADY IN MYLIST", None)
        self.queue.put(create_file_info("/tmp/file1"))
        self.queue.put(None)

        result = client.register_file_infos()

        self.assertEqual(result, [])

    def test_register_file_not_found(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"320 NO SUCH FILE", None)
        file_info = create_file_info("/tmp/file1")
        self.queue.put(file_info)
        self.queue.put(None)

        result = client.register_file_infos()

        self.assertEqual(result, [file_info])

    def test_register_file_timeout(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.side_effect = socket.timeout("timed out")
        file_info = create_file_info("/tmp/file1")
        self.queue.put(file_info)
        self.queue.put(None)

        result = client.register_file_infos()

        self.assertEqual(result, [file_info])

    def test_socket_closed_on_exit(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"210 MYLIST ENTRY ADDED", None)
        client.__exit__()

        self.socket_mock.close.assert_called_once()

    def test_socket_closed_even_if_logout_fails(self):
        client = self._enter_client()
        self.socket_mock.sendto.side_effect = OSError("network error")

        with self.assertRaises(OSError):
            client.__exit__()

        self.socket_mock.close.assert_called_once()

    def test_shutdown_event_stops_processing(self):
        client = self._enter_client()
        self.shutdown_event.set()
        self.queue.put(create_file_info("/tmp/file1"))

        result = client.register_file_infos()

        self.assertEqual(result, [])

    def test_get_mylist_entry(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"221 MYLIST\n42|2660|40|12|1|1532983833|2|1532983833|||\n", None)

        entry = client.get_mylist_entry("/tmp/file1", 1337, "1" * 32)

        self.assertEqual(MylistEntry(lid=42, watched=True, internal=False, view_date=1532983833.0), entry)
        sent = self.socket_mock.sendto.call_args.args[0]
        self.assertEqual(b"MYLIST size=1337&ed2k=" + b"1" * 32 + b"&s=abc123", sent)

    def test_get_mylist_entry_not_in_mylist(self):
        client = self._enter_client()
        for reply in (b"321 NO SUCH ENTRY", b"320 NO SUCH FILE"):
            with self.subTest(reply=reply):
                self.socket_mock.recvfrom.return_value = (reply, None)

                self.assertIsNone(client.get_mylist_entry("/tmp/file1", 1337, "1" * 32))

    def test_get_mylist_entry_timeout(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.side_effect = socket.timeout("timed out")

        self.assertIsNone(client.get_mylist_entry("/tmp/file1", 1337, "1" * 32))

    def test_delete_mylist_entry(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"211 MYLIST ENTRY DELETED\n1\n", None)

        self.assertTrue(client.delete_mylist_entry("/tmp/file1", 1337, "1" * 32))
        sent = self.socket_mock.sendto.call_args.args[0]
        self.assertEqual(b"MYLISTDEL size=1337&ed2k=" + b"1" * 32 + b"&s=abc123", sent)

    def test_delete_mylist_entry_not_in_mylist(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"411 NO SUCH MYLIST ENTRY", None)

        self.assertFalse(client.delete_mylist_entry("/tmp/file1", 1337, "1" * 32))

    def test_delete_mylist_entry_timeout(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.side_effect = socket.timeout("timed out")

        self.assertFalse(client.delete_mylist_entry("/tmp/file1", 1337, "1" * 32))

    def test_verbose_output_does_not_contain_the_password(self):
        """Regression test: -v used to echo the AUTH datagram, password included."""
        self.socket_mock.recvfrom.return_value = self._login_response()
        config = {**self.config, "password": "hunter2"}
        client = UdpClient(self.shutdown_event, True, config, self.queue)

        with patch("builtins.print") as print_mock:
            client.__enter__()

        printed = " ".join(str(arg) for c in print_mock.call_args_list for arg in c.args)
        self.assertIn("Sending", printed)
        self.assertIn("user=user", printed)
        self.assertNotIn("hunter2", printed)
        self.assertIn("pass=***", printed)

    def test_register_replacement_adds_a_new_entry(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"210 MYLIST ENTRY ADDED", None)

        self.assertTrue(client.register_replacement(create_file_info("/tmp/file1")))
        self.assertEqual(2, self.socket_mock.sendto.call_count)  # AUTH, MYLISTADD
        self.assertNotIn(b"edit=1", self.socket_mock.sendto.call_args.args[0])

    def test_register_replacement_edits_an_existing_entry(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.side_effect = [
            (b"310 FILE ALREADY IN MYLIST", None),
            (b"311 MYLIST ENTRY EDITED", None),
        ]

        self.assertTrue(client.register_replacement(create_file_info("/tmp/file1")))
        first, second = (c.args[0] for c in self.socket_mock.sendto.call_args_list[1:])
        self.assertNotIn(b"edit=1", first)
        self.assertIn(b"&edit=1", second)
        self.assertIn(b"viewdate=1532983833", second)

    def test_register_replacement_of_unknown_file(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"320 NO SUCH FILE", None)

        self.assertFalse(client.register_replacement(create_file_info("/tmp/file1")))
        self.assertEqual(2, self.socket_mock.sendto.call_count)

    def test_register_replacement_timeout_on_edit(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.side_effect = [(b"310 FILE ALREADY IN MYLIST", None), socket.timeout("timed out")]

        self.assertFalse(client.register_replacement(create_file_info("/tmp/file1")))

    def test_register_replacement_unexpected_reply_to_edit(self):
        client = self._enter_client()
        self.socket_mock.recvfrom.side_effect = [
            (b"310 FILE ALREADY IN MYLIST", None),
            (b"411 NO SUCH MYLIST ENTRY", None),
        ]

        with self.assertRaises(AnidbProtocolException):
            client.register_replacement(create_file_info("/tmp/file1"))

    def test_plain_registration_never_edits(self):
        """Moving a file again must not overwrite the watch date of its existing entry."""
        client = self._enter_client()
        self.socket_mock.recvfrom.return_value = (b"310 FILE ALREADY IN MYLIST", None)
        self.queue.put(create_file_info("/tmp/file1"))
        self.queue.put(None)

        self.assertEqual([], client.register_file_infos())
        self.assertEqual(2, self.socket_mock.sendto.call_count)
        self.assertNotIn(b"edit=1", self.socket_mock.sendto.call_args.args[0])
