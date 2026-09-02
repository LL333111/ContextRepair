from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def localization_metrics(
    relevant_files: set[str],
    relevant_lines: dict[str, set[int]],
    inspected_files: set[str],
    inspected_regions: Iterable[tuple[str, int, int]],
    context_tokens: int,
) -> dict:
    normalized_relevant = {path.replace("\\", "/") for path in relevant_files}
    normalized_inspected = {path.replace("\\", "/") for path in inspected_files}
    relevant_line_pairs = {
        (path.replace("\\", "/"), line)
        for path, lines in relevant_lines.items()
        for line in lines
    }
    covered_pairs: set[tuple[str, int]] = set()
    for path, start, end in inspected_regions:
        normalized = path.replace("\\", "/")
        covered_pairs.update(
            pair for pair in relevant_line_pairs if pair[0] == normalized and start <= pair[1] <= end
        )
    found_files = normalized_relevant & normalized_inspected
    relevant_units = len(found_files) + len(covered_pairs)
    return {
        "relevant_file_recall": len(found_files) / len(normalized_relevant) if normalized_relevant else None,
        "relevant_line_coverage": (
            len(covered_pairs) / len(relevant_line_pairs) if relevant_line_pairs else None
        ),
        "relevant_files_found": len(found_files),
        "relevant_lines_found": len(covered_pairs),
        "relevant_context_per_1k_tokens": (
            relevant_units * 1000 / context_tokens if context_tokens else None
        ),
        "context_tokens": context_tokens,
    }


def mechanism_comparison(
    *,
    relevant_files: set[str],
    relevant_lines: dict[str, set[int]],
    initial_trajectory: list[dict[str, Any]],
    context_delta: dict[str, Any],
) -> dict[str, Any]:
    initial_files, initial_regions, initial_tokens = _initial_context(initial_trajectory)
    delta_files = {str(path).replace("\\", "/") for path in context_delta.get("new_files", [])}
    delta_regions = [
        (str(item["path"]), int(item["start_line"]), int(item["end_line"]))
        for item in context_delta.get("new_code_regions", [])
    ]
    delta_tokens = int(context_delta.get("token_cost", 0))
    initial = localization_metrics(
        relevant_files, relevant_lines, initial_files, initial_regions, initial_tokens
    )
    after = localization_metrics(
        relevant_files,
        relevant_lines,
        initial_files | delta_files,
        [*initial_regions, *delta_regions],
        initial_tokens + delta_tokens,
    )
    relevant_normalized = {path.replace("\\", "/") for path in relevant_files}
    initial_relevant = initial_files & relevant_normalized
    after_relevant = (initial_files | delta_files) & relevant_normalized
    return {
        "initial": initial,
        "after_reexploration": after,
        "new_relevant_files": sorted(after_relevant - initial_relevant),
        "new_context_tokens": delta_tokens,
    }


def _initial_context(
    trajectory: list[dict[str, Any]],
) -> tuple[set[str], list[tuple[str, int, int]], int]:
    files: set[str] = set()
    regions: list[tuple[str, int, int]] = []
    tokens = 0
    for event in trajectory:
        if event.get("action_type") != "read":
            continue
        tokens += max(1, len(str(event.get("content", ""))) // 4)
        metadata = event.get("metadata", {})
        start = int(metadata.get("start_line") or 1)
        end = int(metadata.get("end_line") or start)
        for path in event.get("files", []):
            normalized = str(path).replace("\\", "/")
            files.add(normalized)
            regions.append((normalized, start, end))
    return files, regions, tokens
