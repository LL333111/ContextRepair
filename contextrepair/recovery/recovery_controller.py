from __future__ import annotations

import json
from pathlib import Path

from contextrepair.agent.base import CodingAgent
from contextrepair.agent.model_client import ModelClient
from contextrepair.config import ExperimentConfig
from contextrepair.logging import TrajectoryLogger
from contextrepair.recovery.context_delta import ContextDeltaBuilder
from contextrepair.recovery.failure_analyzer import (
    FailureAnalyzer,
    extract_failure_checklist,
    extract_repository_paths,
    extract_stack_trace,
    extract_test_evidence,
)
from contextrepair.recovery.reexplorer import FailureConditionedReExplorer
from contextrepair.repository.history import ExplorationHistory
from contextrepair.tools import ShellTool
from contextrepair.types import AgentOutcome


class RecoveryController:
    def __init__(self, model: ModelClient, config: ExperimentConfig):
        self.model = model
        self.config = config

    def recover(
        self,
        *,
        root: Path,
        task_dir: Path,
        issue: str,
        test_command: str,
        initial: AgentOutcome,
        shell: ShellTool | None = None,
    ) -> AgentOutcome:
        events = TrajectoryLogger.load(initial.trajectory_path)
        history = ExplorationHistory.from_trajectory(events)
        history.files.update(initial.files_seen)
        history.symbols.update(initial.symbols_seen)
        history.commands.extend(initial.commands_run)

        analysis = FailureAnalyzer(self.model).analyze(
            issue=issue,
            trajectory=events,
            previous_patch=initial.patch,
            test_output=initial.test_output,
            stack_trace=extract_stack_trace(initial.test_output),
            files_seen=initial.files_seen,
            symbols_seen=initial.symbols_seen,
            commands_run=initial.commands_run,
            previous_hypothesis=initial.hypothesis,
            use_execution_evidence=self.config.recovery.use_execution_evidence,
        )
        analysis.candidate_files = list(
            dict.fromkeys(
                analysis.candidate_files
                + extract_repository_paths(initial.test_output, root)
            )
        )
        analysis = FailureConditionedReExplorer(self.model).plan(
            issue=issue,
            analysis=analysis,
            history=history,
            history_aware=self.config.recovery.history_aware,
            max_actions=self.config.recovery.max_search_actions,
        )
        _write_json(task_dir / "recovery_analysis.json", analysis.to_dict())

        delta = ContextDeltaBuilder(root, self.config.recovery).build(analysis, history)
        _write_json(task_dir / "context_delta.json", delta.to_dict())
        context = json.dumps(
            {
                "previous_attempt": {
                    "summary": initial.final_message,
                    "hypothesis": initial.hypothesis,
                    "test_output": extract_test_evidence(initial.test_output),
                },
                "failure_checklist": extract_failure_checklist(initial.test_output),
                "completion_criterion": (
                    "The repair must address every distinct failure in the checklist, not only "
                    "the first example, and must preserve already passing related cases. "
                    "anchor_code_regions contain exact current workspace text after the first "
                    "attempt; use those snippets as the source of truth for replace/patch context."
                ),
                "failure_analysis": analysis.to_dict(),
                "context_delta": delta.to_dict(),
            },
            ensure_ascii=False,
        )
        # Failure analysis and re-exploration are shared recovery overhead. They count
        # against the experiment-wide hard budget, but must not consume the coding
        # attempt's own allowance before that attempt has even started.
        recovery_start_tokens = self.model.budget.usage.total_tokens
        trajectory = TrajectoryLogger(task_dir / "recovery_trajectory.json", "recovery")
        agent = CodingAgent(
            root,
            self.model,
            self.config.agent,
            trajectory,
            "recovery",
            shell=shell,
            attempt_token_budget=(
                self.config.budget.max_tokens_per_attempt
                or max(
                    1,
                    self.config.budget.max_total_tokens
                    // self.config.budget.max_attempts,
                )
            ),
            attempt_start_tokens=recovery_start_tokens,
            preloaded_regions=[
                (region.path, region.start_line, region.end_line)
                for region in [
                    *delta.anchor_code_regions,
                    *delta.new_code_regions,
                ]
            ],
        )
        return agent.run(issue, test_command, extra_context=context)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
