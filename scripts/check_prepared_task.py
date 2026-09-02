from __future__ import annotations

import argparse
import json
from pathlib import Path

from contextrepair.repository.workspace import WorkspaceManager
from contextrepair.tools.docker_shell import OFFICIAL_EVAL_COMMAND, DockerShellTool


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-file", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, default=Path(".cache/preflight"))
    args = parser.parse_args()
    record = json.loads(args.tasks_file.read_text(encoding="utf-8").splitlines()[0])
    task_root = args.work_root / record["instance_id"]
    workspace_manager = WorkspaceManager(Path(record["repo_path"]), task_root)
    workspace = workspace_manager.create("workspace", record["base_commit"])
    metadata = record["metadata"]
    shell = DockerShellTool(
        workspace,
        image=metadata["docker_image"],
        eval_script=metadata["eval_script"],
        timeout_seconds=120,
        official_timeout_seconds=1800,
        max_output_chars=200_000,
    )
    try:
        python_code, python_output = shell.run("python --version")
        # WorkspaceManager already verifies cleanliness on the host. Running git status
        # inside a Docker Desktop bind mount can spend minutes refreshing file metadata.
        status_code, status_output = 0, ""
        eval_code, eval_output = shell.run(OFFICIAL_EVAL_COMMAND)
        version_code, version_output = shell.run(
            "python -m pip show setuptools-scm; "
            "test -f src/_pytest/_version.py; "
            "printf 'version_file_exit=%s\\n' $?"
        )
    finally:
        shell.close()
        workspace_manager.cleanup()
    payload = {
        "instance_id": record["instance_id"],
        "container_python_exit": python_code,
        "container_python": python_output.strip(),
        "container_git_status_exit": status_code,
        "container_git_status_clean": not status_output.strip(),
        "container_git_status": status_output,
        "unpatched_eval_exit": eval_code,
        "unpatched_eval_failed_as_expected": eval_code != 0,
        "unpatched_eval_tail": eval_output[-10_000:],
        "version_diagnostic_exit": version_code,
        "version_diagnostic": version_output,
        "hidden_eval_script_visible_in_workspace": (
            workspace / "contextrepair_eval.sh"
        ).exists(),
    }
    print(json.dumps(payload, indent=2))
    if python_code != 0 or status_code != 0 or status_output.strip() or eval_code == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
