from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contextrepair.agent.base import parse_json_object
from contextrepair.agent.model_client import ModelClient
from contextrepair.types import FailureAnalysis

FAILURE_TYPES = [
    "wrong_localization",
    "missing_cross_file_dependency",
    "incorrect_causal_hypothesis",
    "incomplete_fix",
    "regression",
    "api_behavior_misunderstanding",
    "environment_test_failure",
    "insufficient_evidence",
]


class FailureAnalyzer:
    def __init__(self, model: ModelClient):
        self.model = model

    def analyze(
        self,
        *,
        issue: str,
        trajectory: list[dict[str, Any]],
        previous_patch: str,
        test_output: str,
        stack_trace: str,
        files_seen: list[str],
        symbols_seen: list[str],
        commands_run: list[str],
        previous_hypothesis: str,
        use_execution_evidence: bool = True,
    ) -> FailureAnalysis:
        evidence = (
            extract_test_evidence(test_output)
            if use_execution_evidence
            else "[withheld for no-execution-evidence ablation]"
        )
        compact_trajectory = [
            {
                "step": event.get("step"),
                "action_type": event.get("action_type"),
                "content": _clip(str(event.get("content", "")), 500),
                "files": event.get("files", []),
                "symbols": event.get("symbols", []),
            }
            for event in trajectory[-24:]
        ]
        prompt = {
            "issue": issue,
            "previous_hypothesis": previous_hypothesis,
            "files_seen": files_seen,
            "symbols_seen": symbols_seen,
            "commands_run": commands_run[-16:],
            "previous_patch": _clip(previous_patch, 6_000),
            "test_output": evidence,
            "stack_trace": (
                _clip(stack_trace, 3_000) if use_execution_evidence else "[withheld]"
            ),
            "trajectory": compact_trajectory,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "Analyze why a repository repair failed. Diagnose evidence and missing context, "
                    "but do not propose code changes. Return one JSON object with keys: "
                    "failure_summary, failure_type, contradicted_assumptions, "
                    "missing_context_hypotheses, candidate_files, candidate_symbols, "
                    "search_actions, priority, rationale. failure_type must be one of: "
                    + ", ".join(FAILURE_TYPES)
                    + ". search_actions are read/search actions only."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ]
        parsed = self._generate_json(messages)
        analysis = FailureAnalysis.from_dict(parsed)
        if analysis.failure_type not in FAILURE_TYPES:
            analysis.failure_type = "insufficient_evidence"
        return analysis

    def _generate_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        response = self.model.generate(
            messages,
            max_tokens=2048,
            thinking=False,
            json_mode=True,
        )
        try:
            return parse_json_object(response.content)
        except (TypeError, ValueError):
            pass
        fallback = self.model.generate(
            messages,
            max_tokens=2048,
            thinking=False,
            json_mode=True,
        )
        return parse_json_object(fallback.content)


def extract_stack_trace(test_output: str) -> str:
    """Extract traceback-shaped evidence without making any repair decision."""
    markers = ("Traceback (most recent call last):", "FAILURES", "ERRORS")
    starts = [test_output.rfind(marker) for marker in markers]
    start = max(starts)
    if start < 0:
        return ""
    return test_output[start:][-12_000:]


def extract_test_evidence(test_output: str) -> str:
    """Keep the scored test region and discard verbose environment setup logs."""
    start_marker = ">>>>> Start Test Output"
    end_marker = ">>>>> End Test Output"
    start = test_output.find(start_marker)
    end = test_output.find(end_marker, start + len(start_marker)) if start >= 0 else -1
    if start >= 0 and end >= 0:
        return _clip(test_output[start : end + len(end_marker)], 8_000)
    return _clip(test_output, 8_000)


def extract_failure_checklist(test_output: str) -> list[str]:
    """Extract compact, provider-independent failure obligations from test output."""
    checklist: list[str] = []
    for line in test_output.splitlines():
        stripped = line.strip()
        if stripped.startswith(
            ("FAIL:", "ERROR:", "AssertionError:")
        ) and stripped not in checklist:
            checklist.append(stripped)
    return checklist[:50]


def extract_repository_paths(test_output: str, root: Path) -> list[str]:
    """Resolve traceback file paths that point into the current repository."""
    paths: list[str] = []
    for match in re.finditer(r"(?:[A-Za-z]:)?[/\\][^\s\"']+?\.py", test_output):
        raw = match.group(0).replace("\\", "/")
        candidates = [raw.lstrip("/")]
        if "/testbed/" in raw:
            candidates.insert(0, raw.split("/testbed/", 1)[1])
        for candidate in candidates:
            target = root / candidate
            if target.is_file():
                normalized = candidate.replace("\\", "/")
                if normalized not in paths:
                    paths.append(normalized)
                break
    return paths


def _clip(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    half = (limit - 32) // 2
    return value[:half] + "\n...[evidence clipped]...\n" + value[-half:]
