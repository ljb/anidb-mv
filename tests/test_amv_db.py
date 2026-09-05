import sys
from unittest import TestCase
from unittest.mock import ANY, call, patch

from conftest import create_file_info

from amv import amv_db
from amv.file_info import FileInfo


class AmvDbRetryTest(TestCase):
    def setUp(self):
        self.client_mock = patch("amv.amv.UdpClient").start()
        self.remove_files_mock = patch("amv.database.remove_files").start()
        self.get_unregistered_files_mock = patch("amv.database.get_unregistered_files", return_value=[]).start()

        patch("amv.database.open_database").start()
        # amv_db does "from .amv import read_config, setup_shutdown_event", so the names
        # to patch live in amv.amv_db. Patching amv.amv leaves these calls untouched, and
        # the tests then read the developer's real ~/.amvrc -- which is why they passed
        # locally and failed in CI, where no config file exists.
        patch(
            "amv.amv_db.read_config",
            return_value={"username": "u", "password": "p", "local_port": 9000},
        ).start()
        patch("amv.amv_db.setup_shutdown_event").start()

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


class AmvDbReplaceTest(TestCase):
    BROKEN_ED2K = "1" * 32
    NEW_ED2K = "2" * 32
    BROKEN_SIZE = 1337
    NEW_SIZE = 4242

    def setUp(self):
        self.client_mock = patch("amv.amv.UdpClient").start()
        self.move_mock = patch("amv.amv_db.shutil.move").start()
        self.os_remove_mock = patch("amv.amv_db.os.remove").start()
        self.remove_files_mock = patch("amv.database.remove_files").start()
        self.get_unregistered_files_mock = patch(
            "amv.database.get_unregistered_files",
            return_value=[create_file_info("/old/stale-path.mkv", id_=1)],
        ).start()

        patch("amv.database.open_database").start()
        # amv_db does "from .amv import read_config, setup_shutdown_event", so the names
        # to patch live in amv.amv_db. Patching amv.amv leaves these calls untouched, and
        # the tests then read the developer's real ~/.amvrc -- which is why they passed
        # locally and failed in CI, where no config file exists.
        patch(
            "amv.amv_db.read_config",
            return_value={"username": "u", "password": "p", "local_port": 9000},
        ).start()
        patch("amv.amv_db.setup_shutdown_event").start()
        patch("amv.amv_db.os.path.isfile", return_value=True).start()
        patch("amv.amv_db.os.path.getsize", side_effect=self._fake_getsize).start()
        patch("amv.amv_db.ed2k_of_path", side_effect=self._fake_ed2k).start()

        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = []

        self.addCleanup(patch.stopall)

    @classmethod
    def _fake_ed2k(cls, path):
        return cls.NEW_ED2K if "new" in path else cls.BROKEN_ED2K

    @classmethod
    def _fake_getsize(cls, path):
        return cls.NEW_SIZE if "new" in path else cls.BROKEN_SIZE

    @patch("sys.argv", ["amv-db", "replace", "/anime/broken.mkv", "/dl/new.mkv"])
    def test_replace_happy_path(self):
        amv_db.main()

        self.remove_files_mock.assert_has_calls([call(ANY, [1])])
        self.move_mock.assert_called_once_with("/dl/new.mkv", "/anime/new.mkv")
        self.os_remove_mock.assert_called_once_with("/anime/broken.mkv")

    @patch("sys.argv", ["amv-db", "replace", "/anime/broken.mkv", "/dl/new.mkv"])
    def test_replace_inherits_view_date_and_flags_from_db(self):
        self.get_unregistered_files_mock.return_value = [
            FileInfo(
                id=42,
                view_date=999999.0,
                watched=False,
                internal=False,
                path="/wherever/stale.mkv",
                size=self.BROKEN_SIZE,
                ed2k=self.BROKEN_ED2K,
            ),
        ]

        amv_db.main()

        client_args = self.client_mock.call_args.args
        queued_file_info = client_args[3].get()
        self.assertEqual(queued_file_info.path, "/dl/new.mkv")
        self.assertEqual(queued_file_info.size, self.NEW_SIZE)
        self.assertEqual(queued_file_info.ed2k, self.NEW_ED2K)
        self.assertEqual(queued_file_info.view_date, 999999.0)
        self.assertFalse(queued_file_info.watched)
        self.assertFalse(queued_file_info.internal)
        self.remove_files_mock.assert_has_calls([call(ANY, [42])])

    @patch("sys.argv", ["amv-db", "replace", "/anime/broken.mkv", "/dl/new.mkv"])
    def test_replace_no_db_match_exits_without_changes(self):
        self.get_unregistered_files_mock.return_value = []

        with self.assertRaises(SystemExit):
            amv_db.main()

        self.client_mock.assert_not_called()
        self.remove_files_mock.assert_not_called()
        self.move_mock.assert_not_called()
        self.os_remove_mock.assert_not_called()

    @patch("sys.argv", ["amv-db", "replace", "/anime/broken.mkv", "/dl/new.mkv"])
    def test_replace_registration_failure_leaves_everything(self):
        new_file_info = FileInfo(
            path="/dl/new.mkv",
            size=self.NEW_SIZE,
            ed2k=self.NEW_ED2K,
            watched=True,
            internal=True,
            view_date=1532983833.2112887,
        )
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [new_file_info]

        with self.assertRaises(SystemExit):
            amv_db.main()

        self.remove_files_mock.assert_not_called()
        self.move_mock.assert_not_called()
        self.os_remove_mock.assert_not_called()

    @patch("sys.argv", ["amv-db", "replace", "/anime/episode.mkv", "/dl/episode.mkv"])
    def test_replace_with_same_basename_skips_separate_delete(self):
        amv_db.main()

        self.move_mock.assert_called_once_with("/dl/episode.mkv", "/anime/episode.mkv")
        self.os_remove_mock.assert_not_called()

    def test_replace_errors_go_to_stderr(self):
        """Regression test: these used to go to stdout, so redirecting output hid them."""
        cases = [
            (["replace", "/anime/broken.mkv", "/anime/broken.mkv"], "must be different files", None),
            (
                ["replace", "/anime/broken.mkv", "/dl/new.mkv"],
                "is not a file",
                lambda p: p != "/anime/broken.mkv",
            ),
        ]

        for argv, expected, isfile in cases:
            with self.subTest(expected=expected):
                if isfile is not None:
                    patch("amv.amv_db.os.path.isfile", side_effect=isfile).start()
                with patch("sys.argv", ["amv-db", *argv]), patch("builtins.print") as print_mock:
                    with self.assertRaises(SystemExit):
                        amv_db.main()

                call = print_mock.call_args_list[-1]
                self.assertIn(expected, str(call.args[0]))
                self.assertIs(sys.stderr, call.kwargs.get("file"))

    @patch("sys.argv", ["amv-db", "replace", "/anime/broken.mkv", "/anime/broken.mkv"])
    def test_replace_same_path_rejected(self):
        with self.assertRaises(SystemExit):
            amv_db.main()

        self.client_mock.assert_not_called()
        self.remove_files_mock.assert_not_called()
        self.move_mock.assert_not_called()
        self.os_remove_mock.assert_not_called()

    @patch("sys.argv", ["amv-db", "replace", "/anime/broken.mkv", "/dl/new.mkv"])
    def test_replace_existing_file_missing(self):
        patch("amv.amv_db.os.path.isfile", side_effect=lambda p: p != "/anime/broken.mkv").start()

        with self.assertRaises(SystemExit):
            amv_db.main()

        self.client_mock.assert_not_called()
        self.move_mock.assert_not_called()
