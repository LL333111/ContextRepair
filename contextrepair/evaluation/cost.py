from __future__ import annotations


def cost_per_resolved(results: list[dict]) -> float | None:
    resolved = sum(bool(item.get("resolved")) for item in results)
    if not resolved:
        return None
    return sum(float(item.get("cost_usd", 0.0)) for item in results) / resolved


def average_cost(results: list[dict]) -> float:
    if not results:
        return 0.0
    return sum(float(item.get("cost_usd", 0.0)) for item in results) / len(results)

