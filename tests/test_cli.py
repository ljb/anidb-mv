from unittest import TestCase
from unittest.mock import ANY, call, patch

from helpers import create_file_info

from amv import amv


class AmvTest(TestCase):
    def setUp(self):
        self.client_mock = patch("amv.amv.UdpClient").start()
        self.move_mock = patch("shutil.move").start()
        self.remove_files_mock = patch("amv.database.remove_files").start()
        self.add_unregistered_files_mock = patch("amv.database.add_unregistered_files").start()
        self.get_unregistered_files_mock = patch("amv.database.get_unregistered_files", return_value=[]).start()

        patch("amv.database.open_database").start()
        patch("os.path.isdir", side_effect=self._mock_isdir).start()
        patch("os.walk", side_effect=self._mock_walk).start()
        patch("os.path.getsize", return_value=1337).start()
        patch(
            "amv.amv._read_config",
            return_value={
                "username": "test-user",
                "password": "test-password",
                "local_port": 9000,
            },
        ).start()
        patch("amv.amv.ed2k_of_path", return_value="1" * 32).start()
        patch("time.time", return_value=1532983833.2112887).start()
        patch("amv.amv._start_worker_thread", side_effect=self._start_worker_inline).start()

        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = []

        self.addCleanup(patch.stopall)

    @staticmethod
    def _start_worker_inline(shutdown_event, watched, external, file_info_queue, files):
        class _DummyThread:
            @staticmethod
            def join():
                return None

        amv._process_files(
            {
                "watched_time": 1532983833.2112887,
                "watched": watched,
                "internal": not external,
            },
            shutdown_event,
            file_info_queue,
            files,
        )
        return _DummyThread()

    @staticmethod
    def _mock_isdir(path):
        return "dir" in path

    @staticmethod
    def _mock_walk(directory):
        if directory == "dir1":
            return [("dir1", [], ["child_file1", "child_file2"])]
        if directory == "dir2":
            return [("dir2", [], ["child_file3", "child_file4"])]
        raise Exception()

    @patch("sys.argv", ["amv", "dir"])
    def test_too_few_arguments(self):
        with self.assertRaises(SystemExit):
            amv.main()

    @patch("sys.argv", ["amv", "file1", "file2"])
    def test_destination_is_a_file(self):
        with self.assertRaises(SystemExit):
            amv.main()

    @patch("sys.argv", ["amv", "dir1", "dir2", "dir1", "dir3"])
    @patch("amv.amv.Queue")
    def test_source_are_directories(self, queue_mock):
        amv.main()

        queue_mock.return_value.put.assert_has_calls(
            [
                call(create_file_info("dir1/child_file1")),
                call(create_file_info("dir1/child_file2")),
                call(create_file_info("dir2/child_file3")),
                call(create_file_info("dir2/child_file4")),
                call(None),
            ]
        )

        self.move_mock.assert_has_calls([call("dir1", "dir3"), call("dir2", "dir3")])

    @patch("sys.argv", ["amv", "file1", "file2", "dir"])
    def test_unregistered_files_added_to_database(self):
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [
            create_file_info("file1", id_=1),
            create_file_info("file2", id_=2),
        ]

        amv.main()

        self.remove_files_mock.assert_not_called()
        self.add_unregistered_files_mock.assert_has_calls(
            [
                call(
                    ANY,
                    [
                        create_file_info("file1", id_=1),
                        create_file_info("file2", id_=2),
                    ],
                )
            ]
        )

    @patch("sys.argv", ["amv", "-n", "file1", "file2", "dir1"])
    @patch("amv.amv.Queue")
    def test_no_files_moved(self, queue_mock):
        amv.main()

        queue_mock.return_value.put.assert_has_calls(
            [
                call(create_file_info("file1")),
                call(create_file_info("file2")),
                call(create_file_info("dir1/child_file1")),
                call(create_file_info("dir1/child_file2")),
                call(None),
            ]
        )

        self.remove_files_mock.assert_not_called()
        self.move_mock.assert_not_called()
        self.add_unregistered_files_mock.assert_not_called()

    @patch("sys.argv", ["amv", "file3", "file4", "dir"])
    def test_register_file_success_with_files_in_db(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]

        amv.main()

        self.remove_files_mock.assert_has_calls([call(ANY, [1, 2])])
        self.add_unregistered_files_mock.assert_not_called()

        self.move_mock.assert_has_calls([call("file3", "dir"), call("file4", "dir")])

    @patch("sys.argv", ["amv", "file3", "dir"])
    def test_db_files_removed_after_successful_registration(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [
            create_file_info("/tmp/file2", id_=2),
        ]

        amv.main()

        self.remove_files_mock.assert_has_calls([call(ANY, [1])])
        self.add_unregistered_files_mock.assert_not_called()

    @patch("sys.argv", ["amv", "file3", "dir"])
    def test_new_unregistered_files_added_to_db_alongside_existing(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
        ]
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("file3"),
        ]

        amv.main()

        self.remove_files_mock.assert_not_called()
        self.add_unregistered_files_mock.assert_has_calls([call(ANY, [create_file_info("file3")])])

    @patch("sys.argv", ["amv", "file3", "dir"])
    def test_unregistered_kept_in_database_on_failure(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]

        amv.main()

        self.remove_files_mock.assert_not_called()
        self.add_unregistered_files_mock.assert_not_called()

        self.move_mock.assert_has_calls([call("file3", "dir")])
