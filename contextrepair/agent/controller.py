from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from contextrepair.agent.base import CodingAgent
from contextrepair.agent.model_client import ModelClient, create_model_client
from contextrepair.budget import BudgetTracker
from contextrepair.config import ExperimentConfig
from contextrepair.logging import TrajectoryLogger
from contextrepair.recovery.recovery_controller import RecoveryController
from contextrepair.repository.workspace import WorkspaceManager
from contextrepair.run_state import atomic_write_json, atomic_write_text
from contextrepair.tools import DockerShellTool, ShellTool
from contextrepair.types import Task


class ExperimentController:
    """Runs SINGLE, RETRY, or CONTEXTREPAIR under one shared hard budget."""

    def __init__(
        self,
        config: ExperimentConfig,
        results_root: Path,
        model: ModelClient | None = None,
    ):
        self.config = config
        self.results_root = results_root.resolve()
        self.budget = model.budget if model is not None else BudgetTracker(config.budget)
        self.model = model or create_model_client(config.model, self.budget)

    def run(self, task: Task) -> dict:
        task_dir = self.results_root / _safe_id(task.instance_id) / self.config.condition
        if (task_dir / "final_result.json").exists():
            raise FileExistsError(
                f"Completed result already exists at {task_dir}; use a new --results directory"
            )
        if task_dir.exists() and any(task_dir.iterdir()):
            raise FileExistsError(
                f"Incomplete result exists at {task_dir}; archive it before restarting"
            )
        task_dir.mkdir(parents=True, exist_ok=True)
        usage_journal = task_dir / "model_usage.partial.json"
        self.model.set_usage_journal_path(usage_journal)
        workspace_manager = WorkspaceManager(task.repo_path, task_dir)
        initial_root = workspace_manager.create("initial", task.base_commit)
        metadata = {
            "instance_id": task.instance_id,
            "issue": task.issue,
            "source_repo": str(task.repo_path),
            "base_commit": task.base_commit,
            "test_command": task.test_command,
            "condition": self.config.condition,
            "model": asdict(self.config.model),
            "budget": asdict(self.config.budget),
            "recovery": asdict(self.config.recovery),
            "started_at": datetime.now(UTC).isoformat(),
            "task_metadata": task.metadata,
        }
        _write_json(task_dir / "metadata.json", metadata)

        initial_shell = _create_shell(task, initial_root, self.config)
        try:
            initial_trajectory = TrajectoryLogger(
                task_dir / "initial_trajectory.json", "initial"
            )
            initial_agent = CodingAgent(
                initial_root,
                self.model,
                self.config.agent,
                initial_trajectory,
                "initial",
                shell=initial_shell,
                attempt_token_budget=_attempt_token_budget(self.config),
            )
            initial = initial_agent.run(task.issue, task.test_command)
            _write_text(task_dir / "initial.patch", initial.patch)
            _write_text(task_dir / "initial_test.log", initial.test_output)

            final = initial
            final_attempt = "initial"
            recovery_attempted = False
            recovery_error: str | None = None
            if not initial.success and self.config.condition != "single":
                recovery_attempted = True
                try:
                    if self.config.condition == "retry":
                        retry_root = workspace_manager.create("retry", task.base_commit)
                        retry_trajectory = TrajectoryLogger(
                            task_dir / "recovery_trajectory.json", "recovery"
                        )
                        retry_shell = _create_shell(task, retry_root, self.config)
                        try:
                            retry_agent = CodingAgent(
                                retry_root,
                                self.model,
                                self.config.agent,
                                retry_trajectory,
                                "recovery",
                                shell=retry_shell,
                                attempt_token_budget=_attempt_token_budget(self.config),
                            )
                            final = retry_agent.run(task.issue, task.test_command)
                        finally:
                            retry_shell.close()
                    else:
                        final = RecoveryController(self.model, self.config).recover(
                            root=initial_root,
                            task_dir=task_dir,
                            issue=task.issue,
                            test_command=task.test_command,
                            initial=initial,
                            shell=initial_shell,
                        )
                    final_attempt = "recovery"
                    _write_text(task_dir / "recovery.patch", final.patch)
                    _write_text(task_dir / "recovery_test.log", final.test_output)
                except Exception as exc:  # noqa: BLE001 - preserve evidence and continue.
                    recovery_error = f"{type(exc).__name__}: {exc}"
        finally:
            initial_shell.close()

        snapshot = self.budget.snapshot()
        result = {
            "instance_id": task.instance_id,
            "condition": self.config.condition,
            "resolved": final.success,
            "initial_resolved": initial.success,
            "recovery_attempted": recovery_attempted,
            "recovered": bool(recovery_attempted and not initial.success and final.success),
            "final_attempt": final_attempt,
            "recovery_error": recovery_error,
            "model_calls": snapshot.calls,
            "input_tokens": snapshot.input_tokens,
            "output_tokens": snapshot.output_tokens,
            "total_tokens": snapshot.input_tokens + snapshot.output_tokens,
            "cost_usd": snapshot.cost_usd,
            "wall_seconds": snapshot.elapsed_seconds,
            "usage_estimated": snapshot.usage_estimated,
            "patch_sha256": hashlib.sha256(final.patch.encode("utf-8")).hexdigest(),
            "finished_at": datetime.now(UTC).isoformat(),
        }
        _write_text(task_dir / "final.patch", final.patch)
        calls = self.model.call_log
        if not self.config.logging.save_raw_messages:
            calls = [
                {
                    **{key: value for key, value in call.items() if key not in {"messages", "response"}},
                    "messages_sha256": hashlib.sha256(
                        json.dumps(call["messages"], sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    "response_sha256": hashlib.sha256(call["response"].encode("utf-8")).hexdigest(),
                }
                for call in calls
            ]
        _write_json(task_dir / "model_calls.json", {"calls": calls})
        _write_json(task_dir / "final_result.json", result)
        usage_journal.unlink(missing_ok=True)
        workspace_manager.cleanup()
        return result


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", value)


def _create_shell(task: Task, root: Path, config: ExperimentConfig) -> ShellTool:
    image = task.metadata.get("docker_image")
    if not image:
        return ShellTool(
            root,
            config.agent.command_timeout_seconds,
            config.agent.max_tool_output_chars,
        )
    eval_script = task.metadata.get("eval_script")
    if not isinstance(eval_script, str) or not eval_script.strip():
        raise ValueError(f"Docker task lacks eval_script: {task.instance_id}")
    return DockerShellTool(
        root,
        image=str(image),
        eval_script=eval_script,
        timeout_seconds=config.agent.command_timeout_seconds,
        official_timeout_seconds=int(task.metadata.get("eval_timeout_seconds", 1800)),
        max_output_chars=config.agent.max_tool_output_chars,
    )


def _attempt_token_budget(config: ExperimentConfig) -> int:
    configured = config.budget.max_tokens_per_attempt
    if configured is not None:
        return configured
    return max(1, config.budget.max_total_tokens // config.budget.max_attempts)


def _write_json(path: Path, value: dict) -> None:
    atomic_write_json(path, value)


def _write_text(path: Path, value: str) -> None:
    atomic_write_text(path, value)
