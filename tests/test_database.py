from unittest import TestCase

from helpers import create_file_info

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
