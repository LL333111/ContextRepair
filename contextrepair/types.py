from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Phase = Literal["initial", "recovery", "evaluation"]


@dataclass(slots=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    estimated: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ModelResponse:
    content: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Task:
    instance_id: str
    issue: str
    repo_path: Path
    test_command: str
    base_commit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentOutcome:
    success: bool
    patch: str
    test_output: str
    final_message: str
    trajectory_path: Path
    usage: TokenUsage
    files_seen: list[str] = field(default_factory=list)
    symbols_seen: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    hypothesis: str = ""


@dataclass(slots=True)
class FailureAnalysis:
    failure_summary: str
    failure_type: str
    contradicted_assumptions: list[str]
    missing_context_hypotheses: list[str]
    candidate_files: list[str]
    candidate_symbols: list[str]
    search_actions: list[dict[str, Any]]
    priority: list[str]
    rationale: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FailureAnalysis:
        return cls(
            failure_summary=str(value.get("failure_summary", "Insufficient evidence")),
            failure_type=str(value.get("failure_type", "insufficient_evidence")),
            contradicted_assumptions=_string_list(value.get("contradicted_assumptions")),
            missing_context_hypotheses=_string_list(
                value.get("missing_context_hypotheses")
            ),
            candidate_files=_string_list(value.get("candidate_files")),
            candidate_symbols=_string_list(value.get("candidate_symbols")),
            search_actions=[
                item.copy()
                for item in value.get("search_actions", [])
                if isinstance(item, dict)
            ]
            if isinstance(value.get("search_actions", []), list)
            else [],
            priority=_string_list(value.get("priority")),
            rationale=str(value.get("rationale", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


@dataclass(slots=True)
class CodeRegion:
    path: str
    start_line: int
    end_line: int
    content: str
    reason: str = ""


@dataclass(slots=True)
class ContextDelta:
    new_files: list[str] = field(default_factory=list)
    new_symbols: list[str] = field(default_factory=list)
    new_code_regions: list[CodeRegion] = field(default_factory=list)
    anchor_code_regions: list[CodeRegion] = field(default_factory=list)
    new_test_context: list[str] = field(default_factory=list)
    new_dependencies: list[str] = field(default_factory=list)
    token_cost: int = 0
    anchor_token_cost: int = 0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        return value
