from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from amv import amv_db


class AmvDbTest(TestCase):
    def test_format_timestamp(self):
        with patch("amv.amv_db.datetime") as datetime_mock:
            datetime_mock.fromtimestamp.return_value = datetime(2018, 7, 30, 20, 15, 35)
            self.assertEqual(amv_db._format_timestamp(1532974535), "2018-07-30 20:15:35")

    def test_format_size(self):
        test_data = [
            (1023, "1023.0B"),
            (1024, "1.0KiB"),
            (1025, "1.0KiB"),
            (1024**2, "1.0MiB"),
            (1024**3, "1.0GiB"),
            (1024**4, "1.0TiB"),
            (1024**5, "1024.0TiB"),
        ]

        for value, expected in test_data:
            actual = amv_db._format_size(value)
            with self.subTest(value=value):
                self.assertEqual(expected, actual)
