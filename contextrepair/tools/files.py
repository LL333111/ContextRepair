from __future__ import annotations

from pathlib import Path

from contextrepair.tools.common import ToolError, resolve_in_root


class FileTool:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def read(self, path: str, start_line: int = 1, end_line: int = 400) -> str:
        target = resolve_in_root(self.root, path)
        if not target.is_file():
            raise ToolError(f"not a file: {path}")
        if start_line < 1 or end_line < start_line:
            raise ToolError("invalid line range")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = lines[start_line - 1 : end_line]
        return "\n".join(f"{number:>6}  {line}" for number, line in enumerate(selected, start_line))

    def list(self, path: str = ".", max_entries: int = 500) -> str:
        target = resolve_in_root(self.root, path)
        if not target.is_dir():
            raise ToolError(f"not a directory: {path}")
        entries: list[str] = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            suffix = "/" if child.is_dir() else ""
            entries.append(str(child.relative_to(self.root)).replace("\\", "/") + suffix)
            if len(entries) >= max_entries:
                entries.append("... entry limit reached")
                break
        return "\n".join(entries)

