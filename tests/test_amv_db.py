from unittest import TestCase
from unittest.mock import ANY, call, patch

from conftest import create_file_info

from amv import amv_db


class AmvDbRetryTest(TestCase):
    def setUp(self):
        self.client_mock = patch("amv.amv.UdpClient").start()
        self.remove_files_mock = patch("amv.database.remove_files").start()
        self.get_unregistered_files_mock = patch("amv.database.get_unregistered_files", return_value=[]).start()

        patch("amv.database.open_database").start()
        patch(
            "amv.amv.read_config",
            return_value={"username": "u", "password": "p", "local_port": 9000},
        ).start()
        patch("amv.amv.setup_shutdown_event").start()

        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = []

        self.addCleanup(patch.stopall)

    @patch("sys.argv", ["amv-db", "retry"])
    def test_retry_with_empty_database_prints_message(self):
        with patch("builtins.print") as print_mock:
            amv_db.main()

        self.client_mock.assert_not_called()
        self.remove_files_mock.assert_not_called()
        printed = " ".join(str(c.args[0]) for c in print_mock.call_args_list if c.args)
        self.assertIn("No unregistered files in database", printed)

    @patch("sys.argv", ["amv-db", "retry"])
    def test_retry_removes_successfully_registered_files(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [
            create_file_info("/tmp/file2", id_=2),
        ]

        amv_db.main()

        self.remove_files_mock.assert_has_calls([call(ANY, [1])])

    @patch("sys.argv", ["amv-db", "retry"])
    def test_retry_keeps_unregistered_files_in_db(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]

        amv_db.main()

        self.remove_files_mock.assert_not_called()

    @patch("sys.argv", ["amv-db", "retry"])
    def test_retry_queues_db_files_for_registration(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]

        amv_db.main()

        client_args = self.client_mock.call_args.args
        queue = client_args[3]
        queued = []
        while not queue.empty():
            queued.append(queue.get())
        self.assertEqual(
            queued,
            [
                create_file_info("/tmp/file1", id_=1),
                create_file_info("/tmp/file2", id_=2),
                None,
            ],
        )
