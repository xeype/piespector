from __future__ import annotations

from io import StringIO
import unittest
from unittest.mock import patch

from piespector import __version__
from piespector.__main__ import main


class MainTests(unittest.TestCase):
    def test_help_prints_usage_without_launching_app(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        with patch("sys.stdout", stdout), patch("sys.stderr", stderr), patch(
            "piespector.__main__.PiespectorApp.run"
        ) as run_mock, self.assertRaises(SystemExit) as exit_context:
            main(["--help"])

        self.assertEqual(exit_context.exception.code, 0)
        self.assertIn("usage: piespector", stdout.getvalue())
        run_mock.assert_not_called()

    def test_version_prints_version_without_launching_app(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        with patch("sys.stdout", stdout), patch("sys.stderr", stderr), patch(
            "piespector.__main__.PiespectorApp.run"
        ) as run_mock, self.assertRaises(SystemExit) as exit_context:
            main(["--version"])

        self.assertEqual(exit_context.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"piespector {__version__}")
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
