import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from contextrepair.tools.search import SearchTool


class SearchToolTests(unittest.TestCase):
    def test_timeout_becomes_actionable_tool_output(self):
        with TemporaryDirectory() as temporary:
            tool = SearchTool(Path(temporary))
            with patch(
                "contextrepair.tools.search.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["rg"], 60),
            ):
                output = tool.search("needle", glob="*")

        self.assertIn("Search timed out after 60 seconds", output)
        self.assertIn("Narrow the path or glob", output)


if __name__ == "__main__":
    unittest.main()
