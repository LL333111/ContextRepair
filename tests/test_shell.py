import tempfile
import unittest
from pathlib import Path

from contextrepair.tools.shell import ShellTool, command_policy_error


class ShellToolTests(unittest.TestCase):
    def test_rejects_recursive_grep_of_repository_root(self):
        message = command_policy_error('grep -R "needle" -n . || true')
        self.assertIsNotNone(message)
        self.assertIn("search action", message or "")

    def test_allows_recursive_grep_of_scoped_directory(self):
        self.assertIsNone(command_policy_error('grep -R "needle" -n src'))

    def test_rejects_git_status_that_enumerates_untracked_files(self):
        message = command_policy_error("git status --short")
        self.assertIsNotNone(message)
        self.assertIn("--untracked-files=no", message or "")

    def test_allows_git_status_without_untracked_enumeration(self):
        self.assertIsNone(
            command_policy_error("git status --short --untracked-files=no")
        )

    def test_tool_returns_policy_error_without_running_command(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = ShellTool(Path(directory)).run('grep -R "needle" -n .')
        self.assertEqual(code, 2)
        self.assertIn("disabled", output)


if __name__ == "__main__":
    unittest.main()
