import subprocess
import tempfile
import unittest
from pathlib import Path

from contextrepair.tools.editor import EditorTool


class EditorToolTests(unittest.TestCase):
    def test_replaces_one_exact_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "sample.py"
            target.write_text("first\nsecond\nthird\n", encoding="utf-8")
            message = EditorTool(root).replace(
                "sample.py", "second\n", "changed\n"
            )
            self.assertIn("Replaced", message)
            self.assertEqual(
                target.read_text(encoding="utf-8"), "first\nchanged\nthird\n"
            )

    def test_replace_rejects_ambiguous_old_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text("same\nsame\n", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "exactly once"):
                EditorTool(root).replace("sample.py", "same", "changed")

    def test_replace_rejects_identical_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text("same\n", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "identical"):
                EditorTool(root).replace("sample.py", "same", "same")

    def test_patch_rejects_no_file_content_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "sample.py").write_text("same\n", encoding="utf-8")
            patch = (
                "--- a/sample.py\n"
                "+++ b/sample.py\n"
                "@@ -1 +1 @@\n"
                "-same\n"
                "+same\n"
            )
            with self.assertRaisesRegex(Exception, "no file-content changes"):
                EditorTool(root).apply_patch(patch)

    def test_recounts_incorrect_hunk_line_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            target = root / "sample.py"
            target.write_text("first\nsecond\nthird\n", encoding="utf-8")
            patch = (
                "--- a/sample.py\n"
                "+++ b/sample.py\n"
                "@@ -1,99 +1,99 @@\n"
                " first\n"
                "-second\n"
                "+changed\n"
                " third\n"
            )
            EditorTool(root).apply_patch(patch)
            self.assertEqual(target.read_text(encoding="utf-8"), "first\nchanged\nthird\n")


if __name__ == "__main__":
    unittest.main()
