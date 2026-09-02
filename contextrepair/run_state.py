from __future__ import annotations

import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contextrepair.config import ExperimentConfig


def task_condition_dir(results_root: str | Path, instance_id: str, condition: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "__", instance_id)
    return Path(results_root).resolve() / safe_id / condition


def load_completed_result(
    results_root: str | Path, instance_id: str, condition: str
) -> dict[str, Any] | None:
    path = task_condition_dir(results_root, instance_id, condition) / "final_result.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("instance_id") != instance_id or value.get("condition") != condition:
        raise ValueError(f"Completed result identity mismatch: {path}")
    return value


def archive_partial_task(
    results_root: str | Path, instance_id: str, condition: str
) -> Path | None:
    task_dir = task_condition_dir(results_root, instance_id, condition)
    if not task_dir.exists() or (task_dir / "final_result.json").is_file():
        return None
    if not any(task_dir.iterdir()):
        task_dir.rmdir()
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    archive = task_dir.with_name(f"{condition}.interrupted-{stamp}")
    task_dir.replace(archive)
    return archive


def worst_case_task_cost_usd(config: ExperimentConfig) -> float:
    highest_rate = max(
        config.model.input_cost_per_million,
        config.model.output_cost_per_million,
    )
    return config.budget.max_total_tokens * highest_rate / 1_000_000


def consumed_cost_usd(results_root: str | Path) -> tuple[float, float, float]:
    root = Path(results_root)
    completed_cost = 0.0
    for path in root.glob("*/*/final_result.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        completed_cost += float(value.get("cost_usd", 0.0))

    interrupted_cost = 0.0
    for path in root.rglob("model_usage.partial.json"):
        if (path.parent / "final_result.json").is_file():
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        interrupted_cost += sum(
            float(call.get("token_usage", {}).get("cost_usd", 0.0))
            for call in value.get("calls", [])
        )
    return completed_cost + interrupted_cost, completed_cost, interrupted_cost


def write_run_ledger(
    results_root: str | Path,
    *,
    max_total_cost_usd: float | None,
    status: str,
    current_task: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    root = Path(results_root)
    total, completed, interrupted = consumed_cost_usd(root)
    completed_results = list(root.glob("*/*/final_result.json"))
    payload = {
        "status": status,
        "current_task": current_task,
        "error": error,
        "completed_task_conditions": len(completed_results),
        "completed_cost_usd": completed,
        "interrupted_cost_usd": interrupted,
        "consumed_cost_usd": total,
        "max_total_cost_usd": max_total_cost_usd,
        "remaining_cost_usd": (
            max(0.0, max_total_cost_usd - total)
            if max_total_cost_usd is not None
            else None
        ),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(root / "run_ledger.json", payload)
    return payload


def atomic_write_json(path: str | Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False))


def atomic_write_text(path: str | Path, value: str) -> None:
    _atomic_write(path, value)


def _atomic_write(path: str | Path, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(value, encoding="utf-8")
        for attempt in range(8):
            try:
                temporary.replace(target)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(min(0.05 * (2**attempt), 0.5))
    finally:
        temporary.unlink(missing_ok=True)
