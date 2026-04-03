import socket
from queue import Queue
from threading import Event
from unittest import TestCase
from unittest.mock import MagicMock, patch

from conftest import create_file_info

from amv.network.client import UdpClient


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
