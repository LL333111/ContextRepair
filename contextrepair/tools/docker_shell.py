from __future__ import annotations

import re
import shlex
import subprocess
import tempfile
import uuid
from pathlib import Path

from contextrepair.tools.common import ToolError, resolve_in_root, truncate
from contextrepair.tools.shell import ShellTool, command_policy_error

OFFICIAL_EVAL_COMMAND = "__CONTEXTREPAIR_OFFICIAL_EVAL__"


class DockerShellTool(ShellTool):
    """Execute every shell action in a disposable, network-disabled task image."""

    def __init__(
        self,
        root: Path,
        *,
        image: str,
        eval_script: str,
        timeout_seconds: int = 120,
        official_timeout_seconds: int = 1800,
        max_output_chars: int = 30_000,
    ):
        super().__init__(root, timeout_seconds, max_output_chars)
        if not image.startswith("swebench/"):
            raise ToolError(f"Refusing untrusted benchmark image namespace: {image}")
        self.image = image
        self.eval_script = _network_safe_eval_script(
            _record_test_exit_code(eval_script)
        )
        self.official_timeout_seconds = official_timeout_seconds
        self.container_name = f"contextrepair-{uuid.uuid4().hex[:16]}"
        self.eval_container_path = f"/root/.contextrepair-eval-{uuid.uuid4().hex}.sh"
        self._started = False
        self._start()

    def _start(self) -> None:
        self._seed_image_artifacts()
        mount = f"type=bind,source={self.root},target=/testbed"
        command = [
            "docker",
            "create",
            "--name",
            self.container_name,
            "--label",
            "contextrepair.managed=true",
            "--network",
            "none",
            "--env",
            "PIP_NO_BUILD_ISOLATION=1",
            "--cpus",
            "2",
            "--memory",
            "6g",
            "--pids-limit",
            "1024",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,nosuid,size=2g",
            "--mount",
            mount,
            self.image,
            "/bin/bash",
            "-lc",
            "tail -f /dev/null",
        ]
        created = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            check=False,
        )
        if created.returncode != 0:
            raise ToolError(created.stderr.strip() or "failed to create task container")
        started = subprocess.run(
            ["docker", "start", self.container_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        if started.returncode != 0:
            self.close()
            raise ToolError(started.stderr.strip() or "failed to start task container")
        self._started = True

    def _seed_image_artifacts(self) -> None:
        """Restore ignored build products present in the official task image."""
        seed_name = f"{self.container_name}-seed"
        try:
            created = subprocess.run(
                [
                    "docker",
                    "create",
                    "--name",
                    seed_name,
                    "--network",
                    "none",
                    self.image,
                    "/bin/bash",
                    "-lc",
                    "tail -f /dev/null",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
                check=False,
            )
            if created.returncode != 0:
                raise ToolError(created.stderr.strip() or "failed to create seed container")
            started = subprocess.run(
                ["docker", "start", seed_name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            if started.returncode != 0:
                raise ToolError(started.stderr.strip() or "failed to start seed container")
            listed = subprocess.run(
                [
                    "docker",
                    "exec",
                    seed_name,
                    "/bin/bash",
                    "-lc",
                    "cd /testbed && git ls-files --others --ignored --exclude-standard -z",
                ],
                capture_output=True,
                timeout=120,
                check=False,
            )
            if listed.returncode != 0:
                raise ToolError(
                    listed.stderr.decode(errors="replace").strip()
                    or "failed to list image build artifacts"
                )
            image_artifacts = [
                item.decode("utf-8", errors="strict")
                for item in listed.stdout.split(b"\0")
                if item
            ]
            artifacts = _seedable_image_artifacts(image_artifacts)
            if len(artifacts) > 256:
                raise ToolError(
                    "refusing to seed unexpectedly many relevant image artifacts: "
                    f"{len(artifacts)}"
                )
            for relative in artifacts:
                target = resolve_in_root(self.root, relative)
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                copied = subprocess.run(
                    [
                        "docker",
                        "cp",
                        f"{seed_name}:/testbed/{relative}",
                        str(target),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                    check=False,
                )
                if copied.returncode != 0:
                    raise ToolError(
                        copied.stderr.strip()
                        or f"failed to seed image artifact: {relative}"
                    )
        finally:
            subprocess.run(
                ["docker", "rm", "--force", seed_name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )


    def _install_eval_script(self) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                suffix=".sh",
                delete=False,
            ) as temporary:
                temporary.write(self.eval_script)
                temporary_path = Path(temporary.name)
            copied = subprocess.run(
                [
                    "docker",
                    "cp",
                    str(temporary_path),
                    f"{self.container_name}:{self.eval_container_path}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            if copied.returncode != 0:
                raise ToolError(copied.stderr.strip() or "failed to stage evaluation script")
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def run(self, command: str, timeout_seconds: int | None = None) -> tuple[int, str]:
        if not command.strip():
            return 2, "empty command"
        if command != OFFICIAL_EVAL_COMMAND and (
            policy_error := command_policy_error(command)
        ):
            return 2, policy_error
        if command != OFFICIAL_EVAL_COMMAND and _is_read_only_git_command(command):
            return super().run(command, timeout_seconds)
        if command == OFFICIAL_EVAL_COMMAND:
            self._install_eval_script()
            inner = f"/bin/bash {self.eval_container_path}"
            effective_timeout = self.official_timeout_seconds
        else:
            inner = (
                "source /opt/miniconda3/bin/activate && "
                "conda activate testbed && cd /testbed && "
                f"{command}"
            )
            effective_timeout = timeout_seconds or self.timeout_seconds
        try:
            try:
                docker_command = ["docker", "exec"]
                if command == OFFICIAL_EVAL_COMMAND:
                    reinstall = "1" if self._requires_editable_install() else "0"
                    docker_command.extend(
                        ["--env", f"CONTEXTREPAIR_REINSTALL={reinstall}"]
                    )
                docker_command.extend(
                    [
                        self.container_name,
                        "timeout",
                        "--signal=KILL",
                        str(effective_timeout),
                        "/bin/bash",
                        "-lc",
                        inner,
                    ]
                )
                completed = subprocess.run(
                    docker_command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=effective_timeout + 30,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                stdout = (
                    exc.stdout.decode(errors="replace")
                    if isinstance(exc.stdout, bytes)
                    else (exc.stdout or "")
                )
                stderr = (
                    exc.stderr.decode(errors="replace")
                    if isinstance(exc.stderr, bytes)
                    else (exc.stderr or "")
                )
                return 124, truncate(
                    f"Command timed out.\n{stdout}\n{stderr}", self.max_output_chars
                )
        finally:
            if command == OFFICIAL_EVAL_COMMAND:
                self._remove_eval_script()
        output = completed.stdout
        if completed.stderr:
            output += ("\n" if output else "") + completed.stderr
        return_code = completed.returncode
        if command == OFFICIAL_EVAL_COMMAND:
            return_code = _official_exit_code(output)
        return return_code, truncate(output, self.max_output_chars)

    def _requires_editable_install(self) -> bool:
        changed = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--"],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        if changed.returncode != 0:
            return True
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        if untracked.returncode != 0:
            return True
        paths = [*changed.stdout.splitlines(), *untracked.stdout.splitlines()]
        return _requires_reinstall_for_paths(paths)

    def _remove_eval_script(self) -> None:
        subprocess.run(
            [
                "docker",
                "exec",
                self.container_name,
                "rm",
                "-f",
                self.eval_container_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

    def close(self) -> None:
        if not self.container_name:
            return
        subprocess.run(
            ["docker", "rm", "--force", self.container_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        self._started = False


def _seedable_image_artifacts(artifacts: list[str]) -> list[str]:
    """Drop large, reproducible build trees before restoring image artifacts.

    Some SWE-bench images retain a complete ``build/lib`` copy containing
    thousands of source files.  The image-provided editable install does not
    need that duplicate tree, and copying it into every fresh worktree is both
    slow and unsafe.  Keep project-specific ignored artifacts while excluding
    standard packaging, cache, and bytecode outputs that can be regenerated.
    """
    ignored_directories = {
        "build",
        "dist",
        ".eggs",
        ".tox",
        ".nox",
        "__pycache__",
    }
    filtered: list[str] = []
    for artifact in artifacts:
        parts = Path(artifact).parts
        if any(part in ignored_directories for part in parts):
            continue
        if any(part.endswith(".egg-info") for part in parts):
            continue
        if artifact.endswith((".pyc", ".pyo")):
            continue
        filtered.append(artifact)
    return filtered


def _official_exit_code(output: str) -> int:
    matches = re.findall(r">>>>> Test Exit Code:\s*(\d+)", output)
    return int(matches[-1]) if matches else 2


def _record_test_exit_code(eval_script: str) -> str:
    """Capture the test command status before the official cleanup commands."""
    lines = eval_script.splitlines()
    for index, line in enumerate(lines):
        if ">>>>> End Test Output" in line:
            lines[index : index + 1] = [
                "contextrepair_test_exit_code=$?",
                line,
                'echo ">>>>> Test Exit Code: ${contextrepair_test_exit_code}"',
            ]
            return "\n".join(lines) + "\n"
    return eval_script


def _network_safe_eval_script(eval_script: str) -> str:
    """Keep official evaluation offline by reusing image-provided build tooling."""
    replacements = {
        "set -uxo pipefail": "set -uo pipefail",
        "git status": "echo 'ContextRepair: omitted slow worktree status diagnostic'",
        "git show": "git show -s --oneline HEAD",
        "python -m pip install -e .": _conditional_editable_install(
            "python -m pip install --no-build-isolation -e ."
        ),
        "pip install -e .": _conditional_editable_install(
            "pip install --no-build-isolation -e ."
        ),
    }
    lines: list[str] = []
    for line in eval_script.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        ending = line[len(stripped) :]
        if stripped.startswith("git -c core.fileMode=false diff "):
            stripped = "echo 'ContextRepair: omitted slow worktree diff diagnostic'"
        lines.append(replacements.get(stripped, stripped) + ending)
    return "".join(lines)


def _conditional_editable_install(install_command: str) -> str:
    return (
        'if [ "${CONTEXTREPAIR_REINSTALL:-1}" = "1" ]; then '
        f"{install_command}; else "
        "echo 'ContextRepair: reusing image-provided editable install'; fi"
    )


def _requires_reinstall_for_paths(paths: list[str]) -> bool:
    manifests = {
        "pipfile",
        "pipfile.lock",
        "poetry.lock",
        "pyproject.toml",
        "requirements.txt",
        "setup.cfg",
        "setup.py",
    }
    compiled_suffixes = {".c", ".cc", ".cpp", ".cxx", ".pyx"}
    for raw_path in paths:
        path = raw_path.replace("\\", "/").lower().lstrip("./")
        name = path.rsplit("/", 1)[-1]
        suffix = Path(name).suffix
        if name in manifests or path.startswith("requirements/"):
            return True
        if suffix in compiled_suffixes:
            return True
    return False


def _is_read_only_git_command(command: str) -> bool:
    if any(operator in command for operator in ("\n", "&&", "||", ";", "|", ">", "<")):
        return False
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    if len(tokens) < 2 or Path(tokens[0]).name.lower() != "git":
        return False
    return tokens[1] in {
        "branch",
        "diff",
        "grep",
        "log",
        "ls-files",
        "rev-parse",
        "show",
        "status",
    }
