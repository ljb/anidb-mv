from unittest import TestCase
from unittest.mock import call, patch, ANY

from amv import amv
from amv import amv_db
from amv import database


def _create_file_info(path, id_=None):
    return {
        'id': id_,
        'view_date': 1532983833.2112887,
        'internal': True,
        'watched': True,
        'path': path,
        'size': 1337,
        'ed2k': '1' * 32
    }


# TODO: Make tests more stable. They fail sometimes, probably due to the mock library not being thread safe
class AmvTest(TestCase):
    def setUp(self):
        self.client_mock = patch('amv.UdpClient').start()
        self.move_mock = patch('shutil.move').start()
        self.remove_files_mock = patch('database.remove_files').start()
        self.add_unregistered_files_mock = patch('database.add_unregistered_files').start()
        self.get_unregistered_files_mock = patch('database.get_unregistered_files', return_value=[]).start()

        patch('database.open_database').start()
        patch('os.path.isdir', side_effect=self._mock_isdir).start()
        patch('os.walk', side_effect=self._mock_walk).start()
        patch('os.path.getsize', return_value=1337).start()
        patch('amv.ed2k_of_path', return_value='1' * 32).start()
        patch('time.time', return_value=1532983833.2112887).start()

        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = []

        self.addCleanup(patch.stopall)

    @staticmethod
    def _mock_isdir(path):
        return 'dir' in path

    @staticmethod
    def _mock_walk(directory):
        if directory == 'dir1':
            return [('dir1', [], ['child_file1', 'child_file2'])]
        elif directory == 'dir2':
            return [('dir2', [], ['child_file3', 'child_file4'])]
        else:
            raise Exception()

    @patch('sys.argv', ['amv', 'dir'])
    def test_too_few_arguments(self):
        with self.assertRaises(SystemExit):
            amv.main()

    @patch('sys.argv', ['amv', 'file1', 'file2'])
    def test_destination_is_a_file(self):
        with self.assertRaises(SystemExit):
            amv.main()

    @patch('sys.argv', ['amv', 'dir1', 'dir2', 'dir1', 'dir3'])
    @patch('amv.Queue')
    def test_source_are_directories(self, queue_mock):
        amv.main()

        queue_mock.return_value.put.assert_has_calls([
            call(_create_file_info('dir1/child_file1')),
            call(_create_file_info('dir1/child_file2')),
            call(_create_file_info('dir2/child_file3')),
            call(_create_file_info('dir2/child_file4')),
            call(None),
        ])

        self.move_mock.assert_has_calls([
            call('dir1', 'dir3'),
            call('dir2', 'dir3')
        ])

    @patch('sys.argv', ['amv', 'file1', 'file2', 'dir'])
    def test_unregistered_files_added_to_database(self):
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [
            _create_file_info('file1', id_=1),
            _create_file_info('file2', id_=2),
        ]

        amv.main()

        self.remove_files_mock.assert_not_called()
        self.add_unregistered_files_mock.assert_has_calls([call(
            ANY, [
                _create_file_info('file1', id_=1),
                _create_file_info('file2', id_=2),
            ]
        )])

    @patch('sys.argv', ['amv', 'file3', 'file4', 'dir'])
    def test_register_file_success_with_files_in_db(self):
        self.get_unregistered_files_mock.return_value = [
            _create_file_info('/tmp/file1', id_=1),
            _create_file_info('/tmp/file2', id_=2),
        ]
        amv.main()

        self.remove_files_mock.has([call(ANY, [1, 2])])
        self.add_unregistered_files_mock.assert_not_called()

        self.move_mock.assert_has_calls([
            call('file3', 'dir'),
            call('file4', 'dir')
        ])

    @patch('sys.argv', ['amv', 'file3', 'dir'])
    def test_unregistered_kept_in_database_on_failure(self):
        self.get_unregistered_files_mock.return_value = [
            _create_file_info('/tmp/file1', id_=1),
            _create_file_info('/tmp/file2', id_=2),
        ]
        self.client_mock.return_value.__enter__.return_value.register_file_infos.return_value = [
            _create_file_info('/tmp/file1', id_=1),
            _create_file_info('/tmp/file2', id_=2),
        ]
        amv.main()

        self.remove_files_mock.assert_not_called()
        self.add_unregistered_files_mock.assert_not_called()

        self.move_mock.assert_has_calls([
            call('file3', 'dir')
        ])


class AmvDbTest(TestCase):
    def test_format_timestamp(self):
        self.assertEqual(
            amv_db._format_timestamp(1532974535),
            '2018-07-30 20:15:35'
        )

    def test_format_size(self):
        test_data = [
            (1023, '1023.0B'),
            (1024, '1.0KiB'),
            (1025, '1.0KiB'),
            (1024 ** 2, '1.0MiB'),
            (1024 ** 3, '1.0GiB'),
            (1024 ** 4, '1.0TiB'),
            (1024 ** 5, '1024.0TiB'),
        ]

        for value, expected in test_data:
            actual = amv_db._format_size(value)
            with self.subTest(value=value):
                self.assertEqual(expected, actual)


class DatabaseTest(TestCase):
    def test_clear_empty_database(self):
        _ = self
        with database.open_database(':memory:') as cursor:
            database.clear(cursor)

    def test_get_unregistered_empty_database(self):
        with database.open_database(':memory:') as cursor:
            self.assertEqual([], database.get_unregistered_files(cursor))

    def test_crud(self):
        with database.open_database(':memory:') as cursor:
            database.add_unregistered_files(
                cursor, [
                    _create_file_info('/tmp/file1'),
                    _create_file_info('/tmp/file2'),
                    _create_file_info('/tmp/file3'),
                    _create_file_info('/tmp/file4')
                ]
            )

            self.assertEqual(
                database.get_unregistered_files(cursor), [
                    _create_file_info('/tmp/file1', id_=1),
                    _create_file_info('/tmp/file2', id_=2),
                    _create_file_info('/tmp/file3', id_=3),
                    _create_file_info('/tmp/file4', id_=4)
                ]
            )

            database.remove_files(cursor, [2, 3])

            self.assertEqual(
                database.get_unregistered_files(cursor), [
                    _create_file_info('/tmp/file1', id_=1),
                    _create_file_info('/tmp/file4', id_=4)
                ]
            )

            database.clear(cursor)

            self.assertEqual(
                database.get_unregistered_files(cursor),
                []
            )
