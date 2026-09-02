from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from contextrepair.tools.common import ToolError, resolve_in_root, truncate


class SearchTool:
    def __init__(self, root: Path, max_output_chars: int = 30_000):
        self.root = root.resolve()
        self.max_output_chars = max_output_chars

    def search(self, query: str, path: str = ".", glob: str | None = None) -> str:
        if not query:
            raise ToolError("search query is required")
        target = resolve_in_root(self.root, path)
        if shutil.which("rg"):
            command = ["rg", "--line-number", "--color", "never", "--smart-case"]
            if glob:
                command.extend(["--glob", glob])
            command.extend(["--", query, str(target)])
        else:
            command = ["git", "grep", "-n", "--", query]
        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return (
                "Search timed out after 60 seconds. Narrow the path or glob and retry; "
                "do not repeat the same broad search."
            )
        if completed.returncode not in {0, 1}:
            raise ToolError(completed.stderr.strip() or "search failed")
        output = completed.stdout.replace(str(self.root) + "\\", "").replace(str(self.root) + "/", "")
        return truncate(output or "No matches", self.max_output_chars)
