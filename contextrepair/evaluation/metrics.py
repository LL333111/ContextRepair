from __future__ import annotations

from contextrepair.evaluation.cost import average_cost, cost_per_resolved


def aggregate_results(results: list[dict]) -> dict:
    total = len(results)
    resolved = sum(bool(item.get("resolved")) for item in results)
    failed_initially = sum(not bool(item.get("initial_resolved")) for item in results)
    recovered = sum(bool(item.get("recovered")) for item in results)
    return {
        "tasks": total,
        "resolved": resolved,
        "resolved_pct": 100.0 * resolved / total if total else 0.0,
        "initial_failures": failed_initially,
        "recovered": recovered,
        "recovery_pct": 100.0 * recovered / failed_initially if failed_initially else None,
        "avg_input_tokens": _average(results, "input_tokens"),
        "avg_output_tokens": _average(results, "output_tokens"),
        "avg_total_tokens": _average(results, "total_tokens"),
        "avg_cost_usd": average_cost(results),
        "cost_per_resolved_usd": cost_per_resolved(results),
        "avg_wall_seconds": _average(results, "wall_seconds"),
    }


def _average(items: list[dict], key: str) -> float:
    if not items:
        return 0.0
    return sum(float(item.get(key, 0.0)) for item in items) / len(items)

