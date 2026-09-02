from __future__ import annotations

import subprocess
from pathlib import Path

from contextrepair.tools.common import ToolError, resolve_in_root


class EditorTool:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def write(self, path: str, content: str) -> str:
        target = resolve_in_root(self.root, path)
        if target.exists() and target.read_text(encoding="utf-8") == content:
            raise ToolError(f"write would not change {path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        return f"Wrote {path} ({len(content)} characters)"

    def replace(self, path: str, old: str, new: str) -> str:
        if not old:
            raise ToolError("replacement old text is empty")
        if old == new:
            raise ToolError("replacement old and new text are identical")
        target = resolve_in_root(self.root, path)
        content = target.read_text(encoding="utf-8")
        matches = content.count(old)
        if matches != 1:
            raise ToolError(
                f"replacement old text must occur exactly once in {path}; found {matches}"
            )
        with target.open("w", encoding="utf-8", newline="") as stream:
            stream.write(content.replace(old, new, 1))
        return f"Replaced exact text in {path}"

    def apply_patch(self, patch: str) -> str:
        if not patch.strip():
            raise ToolError("patch content is empty")
        targets: dict[Path, bytes | None] = {}
        for line in patch.splitlines():
            if not line.startswith("+++ "):
                continue
            raw_path = line[4:].split("\t", 1)[0]
            if raw_path == "/dev/null":
                continue
            raw_path = raw_path.removeprefix("b/")
            target = resolve_in_root(self.root, raw_path)
            targets[target] = target.read_bytes() if target.exists() else None
        if not targets:
            raise ToolError("patch does not name a target file")
        completed = subprocess.run(
            ["git", "apply", "--recount", "--whitespace=nowarn", "-"],
            cwd=self.root,
            input=patch,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        if completed.returncode != 0:
            raise ToolError(completed.stderr.strip() or "git apply failed")
        changed = any(
            (target.read_bytes() if target.exists() else None) != before
            for target, before in targets.items()
        )
        if not changed:
            raise ToolError("patch applied no file-content changes")
        return "Patch applied"

    def diff(self) -> str:
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=True,
        ).stdout.splitlines()
        if untracked:
            subprocess.run(
                ["git", "add", "--intent-to-add", "--", *untracked],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=True,
            )
        return subprocess.run(
            ["git", "diff", "--binary", "--no-ext-diff"],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=True,
        ).stdout
