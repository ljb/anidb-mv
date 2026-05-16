import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from conftest import create_file_info

from amv import database


class DatabaseTest(TestCase):
    def test_clear_empty_database(self):
        _ = self
        with database.open_database(":memory:") as cursor:
            database.clear(cursor)

    def test_get_unregistered_empty_database(self):
        with database.open_database(":memory:") as cursor:
            self.assertEqual([], database.get_unregistered_files(cursor))

    def test_crud(self):
        with database.open_database(":memory:") as cursor:
            database.add_unregistered_files(
                cursor,
                [
                    create_file_info("/tmp/file1"),
                    create_file_info("/tmp/file2"),
                    create_file_info("/tmp/file3"),
                    create_file_info("/tmp/file4"),
                ],
            )

            self.assertEqual(
                database.get_unregistered_files(cursor),
                [
                    create_file_info("/tmp/file1", id_=1),
                    create_file_info("/tmp/file2", id_=2),
                    create_file_info("/tmp/file3", id_=3),
                    create_file_info("/tmp/file4", id_=4),
                ],
            )

            database.remove_files(cursor, [2, 3])

            self.assertEqual(
                database.get_unregistered_files(cursor),
                [create_file_info("/tmp/file1", id_=1), create_file_info("/tmp/file4", id_=4)],
            )

            database.clear(cursor)

            self.assertEqual(database.get_unregistered_files(cursor), [])


class DefaultDatabasePathTest(TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = self._tmp.name
        patch(
            "amv.database.os.path.expanduser",
            side_effect=lambda p: p.replace("~", self.home),
        ).start()
        self.addCleanup(patch.stopall)

    def test_legacy_path_used_when_present(self):
        legacy = os.path.join(self.home, ".amv.sqlite3")
        open(legacy, "a").close()
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/some/other/place"}):
            self.assertEqual(database._default_database_path(), legacy)

    def test_xdg_data_home_respected(self):
        custom = os.path.join(self.home, "custom-data")
        with patch.dict(os.environ, {"XDG_DATA_HOME": custom}):
            self.assertEqual(
                database._default_database_path(),
                os.path.join(custom, "amv", "amv.sqlite3"),
            )

    def test_falls_back_to_xdg_default(self):
        env = {k: v for k, v in os.environ.items() if k != "XDG_DATA_HOME"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                database._default_database_path(),
                os.path.join(self.home, ".local/share/amv/amv.sqlite3"),
            )

    def test_open_database_creates_parent_directory(self):
        env = {k: v for k, v in os.environ.items() if k != "XDG_DATA_HOME"}
        with patch.dict(os.environ, env, clear=True):
            expected_dir = os.path.join(self.home, ".local/share/amv")
            self.assertFalse(os.path.exists(expected_dir))
            with database.open_database() as cursor:
                cursor.execute("select 1")
            self.assertTrue(os.path.isdir(expected_dir))
