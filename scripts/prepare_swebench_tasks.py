from __future__ import annotations

import argparse
import json
import re
import subprocess
import uuid
from pathlib import Path

from datasets import load_dataset

from contextrepair.evaluation.subsets import load_locked_subset
from contextrepair.run_state import atomic_write_text
from contextrepair.tools.docker_shell import OFFICIAL_EVAL_COMMAND

DATASET_NAME = "SWE-bench/SWE-bench_Verified"


def _safe_repo_name(repo: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", repo)


def _run(command: list[str], *, timeout: int = 3600) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "command failed")
    return completed.stdout.strip()


def _prepare_mirror(root: Path, repo: str, commits: set[str]) -> Path:
    target = (root / f"{_safe_repo_name(repo)}.git").resolve()
    root = root.resolve()
    target.relative_to(root)
    if not target.exists():
        temporary = root / f".{target.name}.partial-{uuid.uuid4().hex[:12]}"
        _run(["git", "clone", "--mirror", f"https://github.com/{repo}.git", str(temporary)])
        temporary.replace(target)
    if _run(["git", "-C", str(target), "rev-parse", "--is-bare-repository"]) != "true":
        raise RuntimeError(f"Prepared source is not a bare mirror: {target}")
    for commit in sorted(commits):
        _run(["git", "-C", str(target), "cat-file", "-e", f"{commit}^{{commit}}"])
    return target


def prepare(subset_path: Path, output: Path, mirrors_root: Path) -> None:
    instance_ids = load_locked_subset(subset_path)
    dataset = load_dataset(DATASET_NAME, split="test")
    selected = {
        str(row["instance_id"]): dict(row)
        for row in dataset
        if str(row["instance_id"]) in set(instance_ids)
    }
    missing = set(instance_ids) - set(selected)
    if missing:
        raise RuntimeError(f"Official dataset is missing instances: {sorted(missing)}")

    commits_by_repo: dict[str, set[str]] = {}
    for row in selected.values():
        commits_by_repo.setdefault(str(row["repo"]), set()).add(str(row["base_commit"]))
    mirrors_root.mkdir(parents=True, exist_ok=True)
    mirrors = {
        repo: _prepare_mirror(mirrors_root, repo, commits)
        for repo, commits in sorted(commits_by_repo.items())
    }

    records = []
    for instance_id in sorted(instance_ids):
        row = selected[instance_id]
        records.append(
            {
                "instance_id": instance_id,
                "issue": row["problem_statement"],
                "repo_path": str(mirrors[str(row["repo"])]),
                "base_commit": row["base_commit"],
                "test_command": OFFICIAL_EVAL_COMMAND,
                "metadata": {
                    "benchmark": DATASET_NAME,
                    "repo": row["repo"],
                    "version": row["version"],
                    "difficulty": row.get("difficulty"),
                    "docker_image": row["image"],
                    "eval_script": row["eval_script"],
                    "eval_timeout_seconds": 1800,
                    "fail_to_pass": row["FAIL_TO_PASS"],
                    "pass_to_pass": row["PASS_TO_PASS"],
                    "log_parser": row["log_parser"],
                    "eval_type": row["eval_type"],
                },
            }
        )
    atomic_write_text(
        output,
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
    )
    print(
        json.dumps(
            {
                "dataset": DATASET_NAME,
                "subset": str(subset_path),
                "tasks": len(records),
                "mirrors": len(mirrors),
                "output": str(output),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mirrors-root", type=Path, default=Path("prepared_repos/mirrors"))
    args = parser.parse_args()
    prepare(args.subset, args.output, args.mirrors_root)


if __name__ == "__main__":
    main()
