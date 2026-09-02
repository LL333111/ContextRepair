import subprocess
import tempfile
import unittest
from pathlib import Path

from contextrepair.repository.workspace import WorkspaceManager


class WorkspaceManagerTests(unittest.TestCase):
    def test_creates_clean_workspace_outside_result_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=source,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=source, check=True
            )
            (source / "sample.py").write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "sample.py"], cwd=source, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=source, check=True)
            result_dir = root / "results" / "task"
            manager = WorkspaceManager(source, result_dir)
            workspace = manager.create("initial")
            self.assertFalse(workspace.is_relative_to(result_dir))
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=workspace,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(status.stdout, "")
            manager.cleanup()
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
