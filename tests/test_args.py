import os
import sys
import tempfile
from unittest import TestCase
from unittest.mock import patch

from amv import amv, amv_db


class AmvParseArgsTest(TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_dir = temp_dir.name

        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.temp_dir)

        os.mkdir("destination")
        open("episode.mkv", "w").close()

    @staticmethod
    def parse(argv):
        with patch("sys.argv", ["amv", *argv]):
            return amv._parse_args()

    def parse_expecting_exit(self, argv):
        """Returns what was printed and to which stream."""
        with patch("builtins.print") as print_mock:
            with self.assertRaises(SystemExit) as context:
                self.parse(argv)

        call = print_mock.call_args_list[-1]
        return context.exception.code, str(call.args[0]), call.kwargs.get("file")

    def test_last_argument_becomes_the_destination(self):
        args = self.parse(["episode.mkv", "destination"])

        self.assertEqual(["episode.mkv"], args.files)
        self.assertEqual("destination", args.directory)

    def test_no_move_does_not_need_a_destination(self):
        args = self.parse(["--no-move", "episode.mkv"])

        self.assertEqual(["episode.mkv"], args.files)
        self.assertIsNone(args.directory)

    def test_missing_destination_is_reported_on_stderr(self):
        """Regression test: this used to go to stdout, so it landed in redirected output."""
        status, message, stream = self.parse_expecting_exit(["episode.mkv"])

        self.assertEqual(1, status)
        self.assertIn("A destination directory is required", message)
        self.assertIs(sys.stderr, stream)

    def test_destination_that_is_not_a_directory_is_reported_on_stderr(self):
        open("other.mkv", "w").close()

        status, message, stream = self.parse_expecting_exit(["episode.mkv", "other.mkv"])

        self.assertEqual(1, status)
        self.assertIn("is not a directory", message)
        self.assertIs(sys.stderr, stream)

    def test_flag_defaults(self):
        args = self.parse(["episode.mkv", "destination"])

        self.assertTrue(args.watched)
        self.assertFalse(args.external)
        self.assertFalse(args.verbose)
        self.assertTrue(args.move)
        self.assertFalse(args.retry_unregistered)

    def test_flags_can_be_toggled(self):
        args = self.parse(["--unwatched", "--external", "-v", "-r", "-n", "episode.mkv"])

        self.assertFalse(args.watched)
        self.assertTrue(args.external)
        self.assertTrue(args.verbose)
        self.assertFalse(args.move)
        self.assertTrue(args.retry_unregistered)


class AmvDbParseArgsTest(TestCase):
    SUBCOMMANDS = ["list", "clear", "remove", "retry", "replace"]

    @staticmethod
    def parse(argv):
        with patch("sys.argv", ["amv-db", *argv]):
            return amv_db._parse_args()

    def test_a_subcommand_is_required(self):
        """Regression test: amv-db with no subcommand used to print nothing and exit 0."""
        with patch("sys.stderr"):
            with self.assertRaises(SystemExit) as context:
                self.parse([])

        self.assertEqual(2, context.exception.code)

    def test_verbose_before_the_subcommand(self):
        """Regression test: -v used to be accepted only after the subcommand."""
        self.assertTrue(self.parse(["-v", "retry"]).verbose)
        self.assertTrue(self.parse(["-v", "replace", "old.mkv", "new.mkv"]).verbose)

    def test_verbose_after_the_subcommand(self):
        self.assertTrue(self.parse(["retry", "-v"]).verbose)
        self.assertTrue(self.parse(["replace", "old.mkv", "new.mkv", "-v"]).verbose)

    def test_verbose_defaults_to_false(self):
        """The shared -v is declared with SUPPRESS, so the attribute has to be filled in."""
        for argv in (["list"], ["clear"], ["retry"], ["remove", "1"], ["replace", "old.mkv", "new.mkv"]):
            with self.subTest(argv=argv):
                self.assertFalse(self.parse(argv).verbose)

    def test_subcommands_have_help_text(self):
        help_text = self._help_text()
        for subcommand in self.SUBCOMMANDS:
            with self.subTest(subcommand=subcommand):
                self.assertRegex(help_text, rf"\n\s+{subcommand}\s+\S")

    @staticmethod
    def _help_text():
        with patch("sys.argv", ["amv-db", "--help"]), patch("sys.stdout") as stdout_mock:
            try:
                amv_db._parse_args()
            except SystemExit:
                pass
        return "".join(str(call.args[0]) for call in stdout_mock.write.call_args_list if call.args)
