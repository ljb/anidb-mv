import sys
from threading import Event
from unittest import TestCase
from unittest.mock import ANY, call, patch

from conftest import create_file_info

from amv import amv
from amv.file_info import FileInfo
from amv.network.messages import MylistEntry


class AmvTest(TestCase):
    def setUp(self):
        self.client_mock = patch("amv.amv.UdpClient").start()
        self.move_mock = patch("amv.amv.shutil.move").start()
        self.remove_files_mock = patch("amv.database.remove_files").start()
        self.add_unregistered_files_mock = patch("amv.database.add_unregistered_files").start()
        self.get_unregistered_files_mock = patch("amv.database.get_unregistered_files", return_value=[]).start()

        patch("amv.database.open_database").start()
        patch("amv.amv.os.path.isdir", side_effect=self._mock_isdir).start()
        patch("amv.amv.os.walk", side_effect=self._mock_walk).start()
        patch("amv.amv.os.path.getsize", return_value=1337).start()
        patch(
            "amv.amv.read_config",
            return_value={
                "username": "test-user",
                "password": "test-password",
                "local_port": 9000,
            },
        ).start()
        patch("amv.amv.ed2k_of_path", return_value="1" * 32).start()
        patch("amv.amv.time.time", return_value=1532983833.2112887).start()
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

    @patch("sys.argv", ["amv", "-R", "file3", "file4", "dir"])
    def test_register_file_success_with_files_in_db(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]

        amv.main()

        self.remove_files_mock.assert_has_calls([call(ANY, [1, 2])])
        self.add_unregistered_files_mock.assert_not_called()

        self.move_mock.assert_has_calls([call("file3", "dir"), call("file4", "dir")])

    @patch("sys.argv", ["amv", "-R", "file3", "dir"])
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

    @patch("sys.argv", ["amv", "-R", "file3", "dir"])
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

    @patch("sys.argv", ["amv", "-R", "file3", "dir"])
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

    @patch("sys.argv", ["amv", "file3", "dir"])
    @patch("amv.amv.Queue")
    def test_db_files_not_retried_by_default(self, queue_mock):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]

        amv.main()

        queued_items = [c.args[0] for c in queue_mock.return_value.put.call_args_list]
        self.assertNotIn(create_file_info("/tmp/file1", id_=1), queued_items)
        self.assertNotIn(create_file_info("/tmp/file2", id_=2), queued_items)
        self.remove_files_mock.assert_not_called()
        self.add_unregistered_files_mock.assert_not_called()

    @patch("sys.argv", ["amv", "file3", "dir"])
    def test_db_summary_printed_when_files_present(self):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]

        with patch("builtins.print") as print_mock:
            amv.main()

        printed_lines = [str(c.args[0]) if c.args else "" for c in print_mock.call_args_list]
        printed = "\n".join(printed_lines)
        self.assertIn("2 unregistered files in database:", printed)
        self.assertIn("/tmp/file1", printed)
        self.assertIn("/tmp/file2", printed)
        self.assertIn("amv-db retry", printed)
        self.assertIn("", printed_lines, "Expected a blank line after the summary")

    @patch("sys.argv", ["amv", "file3", "dir"])
    def test_db_summary_singular_form(self):
        self.get_unregistered_files_mock.return_value = [create_file_info("/tmp/file1", id_=1)]

        with patch("builtins.print") as print_mock:
            amv.main()

        printed = " ".join(str(c.args[0]) for c in print_mock.call_args_list if c.args)
        self.assertIn("1 unregistered file in database", printed)

    @patch("sys.argv", ["amv", "file3", "dir"])
    def test_no_db_summary_when_database_empty(self):
        self.get_unregistered_files_mock.return_value = []

        with patch("builtins.print") as print_mock:
            amv.main()

        printed = " ".join(str(c.args[0]) for c in print_mock.call_args_list if c.args)
        self.assertNotIn("unregistered", printed)

    @patch("sys.argv", ["amv", "-R", "file3", "dir"])
    @patch("amv.amv.Queue")
    def test_retry_flag_queues_db_files(self, queue_mock):
        self.get_unregistered_files_mock.return_value = [
            create_file_info("/tmp/file1", id_=1),
            create_file_info("/tmp/file2", id_=2),
        ]

        amv.main()

        queued_items = [c.args[0] for c in queue_mock.return_value.put.call_args_list]
        self.assertIn(create_file_info("/tmp/file1", id_=1), queued_items)
        self.assertIn(create_file_info("/tmp/file2", id_=2), queued_items)


class AmvReplaceTest(TestCase):
    OLD_ED2K = "1" * 32
    NEW_ED2K = "2" * 32
    OLD_SIZE = 1337
    NEW_SIZE = 4242

    def setUp(self):
        self.client_mock = patch("amv.amv.UdpClient").start()
        self.client = self.client_mock.return_value.__enter__.return_value
        self.client.register_replacement.return_value = True
        self.client.get_mylist_entry.return_value = MylistEntry(lid=7, watched=False, internal=False, view_date=0.0)
        self.client.delete_mylist_entry.return_value = True

        self.move_mock = patch("amv.amv.shutil.move").start()
        self.os_remove_mock = patch("amv.amv.os.remove").start()
        self.remove_files_mock = patch("amv.database.remove_files").start()
        self.get_unregistered_files_mock = patch("amv.database.get_unregistered_files", return_value=[]).start()

        patch("amv.database.open_database").start()
        patch("amv.amv.read_config", return_value={"username": "u", "password": "p", "local_port": 9000}).start()
        self.shutdown_event = Event()
        patch("amv.amv.setup_shutdown_event", return_value=self.shutdown_event).start()
        patch("amv.amv.os.path.isfile", return_value=True).start()
        patch("amv.amv.os.path.getsize", side_effect=self._fake_getsize).start()
        patch("amv.amv.ed2k_of_path", side_effect=self._fake_ed2k).start()

        self.addCleanup(patch.stopall)

    @classmethod
    def _fake_ed2k(cls, path):
        return cls.NEW_ED2K if "new" in path else cls.OLD_ED2K

    @classmethod
    def _fake_getsize(cls, path):
        return cls.NEW_SIZE if "new" in path else cls.OLD_SIZE

    def _registered_file_info(self):
        return self.client.register_replacement.call_args.args[0]

    def _old_in_database(self, **overrides):
        values = dict(id=42, view_date=999999.0, watched=False, internal=False, path="/wherever/stale.mkv")
        values.update(overrides)
        self.get_unregistered_files_mock.return_value = [FileInfo(size=self.OLD_SIZE, ed2k=self.OLD_ED2K, **values)]

    # ---- the existing file is in MyList

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/old.mkv"])
    def test_replace_registered_file(self):
        self.client.get_mylist_entry.return_value = MylistEntry(lid=7, watched=True, internal=False, view_date=12345.0)

        amv.main()

        self.client.get_mylist_entry.assert_called_once_with("/anime/old.mkv", self.OLD_SIZE, self.OLD_ED2K)
        queued = self._registered_file_info()
        self.assertEqual("/dl/new.mkv", queued.path)
        self.assertEqual(self.NEW_SIZE, queued.size)
        self.assertEqual(self.NEW_ED2K, queued.ed2k)
        self.assertTrue(queued.watched)
        self.assertFalse(queued.internal)
        self.assertEqual(12345.0, queued.view_date)
        self.client.delete_mylist_entry.assert_called_once_with("/anime/old.mkv", self.OLD_SIZE, self.OLD_ED2K)
        self.remove_files_mock.assert_not_called()
        self.move_mock.assert_called_once_with("/dl/new.mkv", "/anime/new.mkv")
        self.os_remove_mock.assert_called_once_with("/anime/old.mkv")

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/old.mkv"])
    def test_replace_registers_new_file_before_deleting_the_old_entry(self):
        order = []
        self.client.register_replacement.side_effect = lambda _: order.append("add") or True
        self.client.delete_mylist_entry.side_effect = lambda *_: order.append("delete") or True

        amv.main()

        self.assertEqual(["add", "delete"], order)

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/old.mkv"])
    def test_replace_not_in_database_or_mylist_exits_without_changes(self):
        self.client.get_mylist_entry.return_value = None

        with patch("builtins.print") as print_mock, self.assertRaises(SystemExit) as context:
            amv.main()

        self.assertEqual(1, context.exception.code)
        last = print_mock.call_args_list[-1]
        self.assertIn("neither in the database nor in MyList", str(last.args[0]))
        self.assertIs(sys.stderr, last.kwargs.get("file"))
        self.client.register_replacement.assert_not_called()
        self.client.delete_mylist_entry.assert_not_called()
        self.move_mock.assert_not_called()
        self.os_remove_mock.assert_not_called()

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/old.mkv"])
    def test_replace_registration_failure_keeps_the_old_entry_and_files(self):
        self.client.register_replacement.return_value = False

        with self.assertRaises(SystemExit):
            amv.main()

        self.client.delete_mylist_entry.assert_not_called()
        self.remove_files_mock.assert_not_called()
        self.move_mock.assert_not_called()
        self.os_remove_mock.assert_not_called()

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/old.mkv"])
    def test_replace_interrupted_during_registration_changes_nothing(self):
        """The reply may arrive after Ctrl-C, so a successful registration must not pass for a go-ahead."""
        self.client.register_replacement.side_effect = lambda _: self.shutdown_event.set() or True

        with self.assertRaises(SystemExit):
            amv.main()

        self.client.delete_mylist_entry.assert_not_called()
        self.remove_files_mock.assert_not_called()
        self.move_mock.assert_not_called()
        self.os_remove_mock.assert_not_called()

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/old.mkv"])
    def test_replace_warns_but_moves_when_the_old_entry_cannot_be_deleted(self):
        self.client.delete_mylist_entry.return_value = False

        with patch("builtins.print") as print_mock:
            amv.main()

        warnings = [c for c in print_mock.call_args_list if "remove it by hand" in str(c.args[0])]
        self.assertEqual(1, len(warnings))
        self.assertIs(sys.stderr, warnings[0].kwargs.get("file"))
        self.move_mock.assert_called_once_with("/dl/new.mkv", "/anime/new.mkv")
        self.os_remove_mock.assert_called_once_with("/anime/old.mkv")

    # ---- the existing file is in the database of unregistered files

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/broken.mkv"])
    def test_replace_unregistered_file(self):
        self._old_in_database()

        amv.main()

        self.client.get_mylist_entry.assert_not_called()
        self.client.delete_mylist_entry.assert_not_called()
        self.remove_files_mock.assert_has_calls([call(ANY, [42])])
        self.move_mock.assert_called_once_with("/dl/new.mkv", "/anime/new.mkv")
        self.os_remove_mock.assert_called_once_with("/anime/broken.mkv")

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/broken.mkv"])
    def test_replace_inherits_view_date_and_flags_from_db(self):
        self._old_in_database(view_date=999999.0, watched=False, internal=False)

        amv.main()

        queued = self._registered_file_info()
        self.assertEqual("/dl/new.mkv", queued.path)
        self.assertEqual(self.NEW_SIZE, queued.size)
        self.assertEqual(self.NEW_ED2K, queued.ed2k)
        self.assertEqual(999999.0, queued.view_date)
        self.assertFalse(queued.watched)
        self.assertFalse(queued.internal)

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/broken.mkv"])
    def test_replace_matches_db_entry_by_hash_not_path(self):
        self._old_in_database(path="/moved/since/then.mkv")

        amv.main()

        self.remove_files_mock.assert_has_calls([call(ANY, [42])])

    @patch("sys.argv", ["amv", "-r", "/dl/new.mkv", "/anime/broken.mkv"])
    def test_replace_registration_failure_keeps_db_entry(self):
        self._old_in_database()
        self.client.register_replacement.return_value = False

        with self.assertRaises(SystemExit):
            amv.main()

        self.remove_files_mock.assert_not_called()
        self.move_mock.assert_not_called()
        self.os_remove_mock.assert_not_called()

    # ---- file system checks shared by both paths

    @patch("sys.argv", ["amv", "-r", "/dl/episode.mkv", "/anime/episode.mkv"])
    def test_replace_with_same_basename_skips_separate_delete(self):
        amv.main()

        self.move_mock.assert_called_once_with("/dl/episode.mkv", "/anime/episode.mkv")
        self.os_remove_mock.assert_not_called()

    def test_replace_file_errors_go_to_stderr(self):
        cases = [
            (["/anime/old.mkv", "/anime/old.mkv"], "must be different files", None),
            (["/dl/new.mkv", "/anime/old.mkv"], "/anime/old.mkv is not a file", lambda p: p != "/anime/old.mkv"),
            (["/dl/new.mkv", "/anime/old.mkv"], "/dl/new.mkv is not a file", lambda p: p != "/dl/new.mkv"),
        ]

        for argv, expected, isfile in cases:
            with self.subTest(expected=expected):
                if isfile is not None:
                    patch("amv.amv.os.path.isfile", side_effect=isfile).start()
                with patch("sys.argv", ["amv", "-r", *argv]), patch("builtins.print") as print_mock:
                    with self.assertRaises(SystemExit):
                        amv.main()

                last = print_mock.call_args_list[-1]
                self.assertIn(expected, str(last.args[0]))
                self.assertIs(sys.stderr, last.kwargs.get("file"))
                self.client_mock.assert_not_called()
                self.move_mock.assert_not_called()
