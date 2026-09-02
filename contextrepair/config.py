from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # Minimal source-checkout fallback; installed package uses PyYAML.
    yaml = None


@dataclass(slots=True)
class ModelConfig:
    provider: str
    name: str
    temperature: float = 0.0
    max_tokens: int = 4096
    thinking_enabled: bool = False
    api_key_env: str | None = None
    base_url: str | None = None
    input_cost_per_million: float = 0.0
    output_cost_per_million: float = 0.0


@dataclass(slots=True)
class BudgetConfig:
    max_total_tokens: int = 100_000
    max_tokens_per_attempt: int | None = None
    max_model_calls: int = 30
    max_attempts: int = 2
    max_wall_seconds: int = 1800


@dataclass(slots=True)
class RecoveryConfig:
    enabled: bool = True
    use_execution_evidence: bool = True
    history_aware: bool = True
    max_new_files: int = 8
    max_new_context_tokens: int = 12_000
    max_anchor_files: int = 3
    max_anchor_context_tokens: int = 6_000
    max_search_actions: int = 10


@dataclass(slots=True)
class AgentConfig:
    max_steps: int = 25
    command_timeout_seconds: int = 120
    max_tool_output_chars: int = 30_000
    max_json_repairs: int = 2


@dataclass(slots=True)
class LoggingConfig:
    save_raw_messages: bool = True
    save_tool_output: bool = True
    save_token_usage: bool = True


@dataclass(slots=True)
class ExperimentConfig:
    condition: str
    model: ModelConfig
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    seed: int = 0


def _construct(cls: type, raw: dict[str, Any] | None):
    fields = cls.__dataclass_fields__
    return cls(**{key: value for key, value in (raw or {}).items() if key in fields})


def load_config(path: str | Path) -> ExperimentConfig:
    config_path = Path(path)
    content = config_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(content) if yaml is not None else _minimal_yaml(content)
    raw = raw or {}
    if "model" not in raw:
        raise ValueError("Configuration requires a model section")
    condition = str(raw.get("condition", "contextrepair")).lower()
    if condition not in {"single", "retry", "contextrepair"}:
        raise ValueError(f"Unknown condition: {condition}")
    config = ExperimentConfig(
        condition=condition,
        model=_construct(ModelConfig, raw["model"]),
        budget=_construct(BudgetConfig, raw.get("budget")),
        recovery=_construct(RecoveryConfig, raw.get("recovery")),
        agent=_construct(AgentConfig, raw.get("agent")),
        logging=_construct(LoggingConfig, raw.get("logging")),
        seed=int(raw.get("seed", 0)),
    )
    expected_attempts = 1 if condition == "single" else 2
    if config.budget.max_attempts != expected_attempts:
        raise ValueError(
            f"{condition} requires budget.max_attempts={expected_attempts}, "
            f"got {config.budget.max_attempts}"
        )
    if (condition == "contextrepair") != config.recovery.enabled:
        raise ValueError(
            "recovery.enabled must be true only for the contextrepair condition"
        )
    return config


def _minimal_yaml(content: str) -> dict[str, Any]:
    """Parse the scalar-only mapping subset used by the shipped configs."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for number, original in enumerate(content.splitlines(), 1):
        if not original.strip() or original.lstrip().startswith("#"):
            continue
        indent = len(original) - len(original.lstrip(" "))
        line = original.strip()
        if ":" not in line:
            raise ValueError(f"Unsupported YAML at line {number}")
        key, raw_value = line.split(":", 1)
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        raw_value = raw_value.strip()
        if not raw_value:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        lowered = raw_value.lower()
        if lowered in {"true", "false"}:
            value: Any = lowered == "true"
        elif lowered in {"null", "none", "~"}:
            value = None
        else:
            try:
                value = float(raw_value) if "." in raw_value else int(raw_value)
            except ValueError:
                value = raw_value.strip("\"'")
        parent[key] = value
    return root
