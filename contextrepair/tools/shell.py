from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from contextrepair.tools.common import truncate


class ShellTool:
    def __init__(self, root: Path, timeout_seconds: int = 120, max_output_chars: int = 30_000):
        self.root = root.resolve()
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def close(self) -> None:
        """Release backend resources; the host backend has nothing to release."""

    def run(self, command: str, timeout_seconds: int | None = None) -> tuple[int, str]:
        if not command.strip():
            return 2, "empty command"
        if policy_error := command_policy_error(command):
            return 2, policy_error
        environment = os.environ.copy()
        environment.update({"CI": "1", "PAGER": "cat", "GIT_PAGER": "cat"})
        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds or self.timeout_seconds,
                env=environment,
                check=False,
            )
            output = completed.stdout
            if completed.stderr:
                output += ("\n" if output else "") + completed.stderr
            return completed.returncode, truncate(output, self.max_output_chars)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return 124, truncate(f"Command timed out.\n{stdout}\n{stderr}", self.max_output_chars)


def command_policy_error(command: str) -> str | None:
    """Reject search commands known to stall on large benchmark repositories."""
    for segment in command.replace("&&", ";").replace("||", ";").split(";"):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            continue
        if not tokens:
            continue
        grep_index = next(
            (
                index
                for index, token in enumerate(tokens)
                if Path(token).name.lower() in {"grep", "egrep"}
            ),
            None,
        )
        if grep_index is not None:
            grep_tokens = tokens[grep_index + 1 :]
            recursive = any(
                token == "--recursive"
                or (
                    token.startswith("-")
                    and not token.startswith("--")
                    and "r" in token[1:].lower()
                )
                for token in grep_tokens
            )
            repository_root = any(token in {".", "./"} for token in grep_tokens)
            if recursive and repository_root:
                return (
                    "Repository-wide recursive grep is disabled because it can stall large "
                    "checkouts. Use the search action with a scoped path/glob, or use rg with "
                    "an explicit subdirectory."
                )
        git_status = len(tokens) >= 2 and Path(tokens[0]).name.lower() == "git" and (
            "status" in tokens[1:]
        )
        bounded_untracked_scan = any(
            token in {"-uno", "--untracked-files=no"} for token in tokens
        )
        if git_status and not bounded_untracked_scan:
            return (
                "Unbounded git status is disabled because ignored/untracked enumeration can "
                "stall benchmark checkouts. Use 'git status --short --untracked-files=no'; "
                "use 'git ls-files --others --exclude-standard' only when untracked files are "
                "specifically needed."
            )
    return None
