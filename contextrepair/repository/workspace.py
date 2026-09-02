from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class WorkspaceError(RuntimeError):
    pass


class WorkspaceManager:
    """Creates isolated local clones so attempts never alter the source checkout."""

    def __init__(self, source: Path, task_dir: Path):
        self.source = source.resolve()
        self.task_dir = task_dir.resolve()
        configured_root = os.getenv("CONTEXTREPAIR_WORKSPACE_ROOT")
        temporary_parent: str | None = None
        if configured_root:
            parent = Path(configured_root).expanduser().resolve()
            parent.mkdir(parents=True, exist_ok=True)
            temporary_parent = str(parent)
        self._temporary = tempfile.TemporaryDirectory(
            prefix="contextrepair-workspace-",
            dir=temporary_parent,
        )
        self.workspace_root = Path(self._temporary.name).resolve()

    def create(self, name: str, base_commit: str | None = None) -> Path:
        if not _is_git_repository(self.source):
            raise WorkspaceError(f"Task repository is not a git checkout: {self.source}")
        if not name or any(character in name for character in ("/", "\\", "..")):
            raise WorkspaceError(f"Invalid workspace name: {name!r}")
        destination = (self.workspace_root / name).resolve()
        try:
            destination.relative_to(self.workspace_root)
        except ValueError as exc:
            raise WorkspaceError(f"Workspace escapes task directory: {name!r}") from exc
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={self.source.as_posix()}",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
                str(self.source),
                str(destination),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        if completed.returncode != 0:
            raise WorkspaceError(completed.stderr.strip() or "git clone failed")
        if base_commit:
            checkout = subprocess.run(
                ["git", "checkout", "--quiet", base_commit],
                cwd=destination,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            if checkout.returncode != 0:
                raise WorkspaceError(checkout.stderr.strip() or f"cannot checkout {base_commit}")
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=destination,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        if status.returncode != 0 or status.stdout.strip():
            detail = status.stderr.strip() or status.stdout.strip() or "git status failed"
            raise WorkspaceError(f"Fresh workspace is not clean: {detail}")
        return destination

    def cleanup(self) -> None:
        self._temporary.cleanup()


def _is_git_repository(path: Path) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={path.resolve().as_posix()}",
            "-C",
            str(path),
            "rev-parse",
            "--git-dir",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    return completed.returncode == 0
