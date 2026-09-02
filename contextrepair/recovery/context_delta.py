from __future__ import annotations

import re
from pathlib import Path

from contextrepair.config import RecoveryConfig
from contextrepair.repository.dependencies import python_imports
from contextrepair.repository.history import ExplorationHistory
from contextrepair.repository.symbols import python_symbols
from contextrepair.tools import FileTool, SearchTool
from contextrepair.tools.common import ToolError
from contextrepair.types import CodeRegion, ContextDelta, FailureAnalysis


class ContextDeltaBuilder:
    def __init__(self, root: Path, config: RecoveryConfig):
        self.root = root.resolve()
        self.config = config
        self.files = FileTool(self.root)
        self.search = SearchTool(self.root)

    def build(self, analysis: FailureAnalysis, history: ExplorationHistory) -> ContextDelta:
        delta = ContextDelta()
        seen_regions: set[tuple[str, int, int]] = set()
        anchor_regions: set[tuple[str, int, int]] = set()
        anchor_actions: list[dict] = []
        token_limit = self.config.max_new_context_tokens

        for action in analysis.search_actions:
            if len(delta.new_files) >= self.config.max_new_files or delta.token_cost >= token_limit:
                break
            kind = str(action.get("type", action.get("action", ""))).lower()
            try:
                if kind == "read":
                    path = str(action.get("path", "")).replace("\\", "/")
                    if path and not history.is_new_file(path):
                        anchor_actions.append(action)
                    self._add_read(delta, action, history, seen_regions)
                elif kind == "search":
                    output = self.search.search(
                        str(action.get("query", "")),
                        str(action.get("path", ".")),
                        str(action["glob"]) if action.get("glob") else None,
                    )
                    self._add_search_matches(delta, output, action, history, seen_regions)
            except (ToolError, OSError, ValueError):
                continue

        for path in analysis.candidate_files:
            if len(delta.new_files) >= self.config.max_new_files or delta.token_cost >= token_limit:
                break
            try:
                self._add_read(
                    delta,
                    {"path": path, "start_line": 1, "end_line": 300, "reason": "candidate file"},
                    history,
                    seen_regions,
                )
            except (ToolError, OSError, ValueError):
                continue

        for path in analysis.candidate_files:
            normalized = str(path).replace("\\", "/")
            if normalized and not history.is_new_file(normalized):
                anchor_actions.append(
                    {
                        "path": normalized,
                        "start_line": 1,
                        "end_line": 300,
                        "reason": "current candidate-file anchor",
                    }
                )
        for action in anchor_actions:
            if (
                len({region.path for region in delta.anchor_code_regions})
                >= self.config.max_anchor_files
                or delta.anchor_token_cost >= self.config.max_anchor_context_tokens
            ):
                break
            try:
                self._add_anchor_read(delta, action, anchor_regions)
            except (ToolError, OSError, ValueError):
                continue

        delta.new_files = list(dict.fromkeys(delta.new_files))
        delta.new_symbols = list(dict.fromkeys(delta.new_symbols))
        delta.new_dependencies = list(dict.fromkeys(delta.new_dependencies))
        delta.new_test_context = list(dict.fromkeys(delta.new_test_context))
        delta.summary = (
            f"Acquired {len(delta.new_code_regions)} new regions from "
            f"{len(delta.new_files)} previously unseen files; found "
            f"{len(delta.new_symbols)} new symbols and {len(delta.new_dependencies)} dependencies; "
            f"refreshed {len(delta.anchor_code_regions)} current-file anchor regions."
        )
        return delta

    def _add_anchor_read(
        self,
        delta: ContextDelta,
        action: dict,
        seen_regions: set[tuple[str, int, int]],
    ) -> None:
        """Refresh exact current text without counting it as newly discovered context."""
        path = str(action.get("path", "")).replace("\\", "/")
        if not path:
            return
        start = max(1, int(action.get("start_line", 1)))
        end = max(start, min(start + 499, int(action.get("end_line", start + 250))))
        region_key = (path, start, end)
        if region_key in seen_regions:
            return
        content = self.files.read(path, start, end)
        estimated_tokens = max(1, len(content) // 4)
        remaining = self.config.max_anchor_context_tokens - delta.anchor_token_cost
        if estimated_tokens > remaining:
            content = content[: max(0, remaining * 4)]
            estimated_tokens = max(0, len(content) // 4)
        if not content:
            return
        seen_regions.add(region_key)
        delta.anchor_code_regions.append(
            CodeRegion(path, start, end, content, str(action.get("reason", "")))
        )
        delta.anchor_token_cost += estimated_tokens

    def _add_search_matches(
        self,
        delta: ContextDelta,
        output: str,
        action: dict,
        history: ExplorationHistory,
        seen_regions: set[tuple[str, int, int]],
    ) -> None:
        for line in output.splitlines():
            match = re.match(r"^(.+?):(\d+):", line)
            if not match:
                continue
            path, line_number = match.group(1).replace("\\", "/"), int(match.group(2))
            if Path(path).is_absolute():
                try:
                    path = str(Path(path).resolve().relative_to(self.root)).replace("\\", "/")
                except ValueError:
                    continue
            self._add_read(
                delta,
                {
                    "path": path,
                    "start_line": max(1, line_number - 30),
                    "end_line": line_number + 50,
                    "reason": action.get("reason", f"match for {action.get('query', '')}"),
                },
                history,
                seen_regions,
            )
            if len(delta.new_files) >= self.config.max_new_files:
                break

    def _add_read(
        self,
        delta: ContextDelta,
        action: dict,
        history: ExplorationHistory,
        seen_regions: set[tuple[str, int, int]],
    ) -> None:
        path = str(action.get("path", "")).replace("\\", "/")
        if not path or (self.config.history_aware and not history.is_new_file(path)):
            return
        start = max(1, int(action.get("start_line", 1)))
        end = max(start, min(start + 499, int(action.get("end_line", start + 250))))
        region_key = (path, start, end)
        if region_key in seen_regions:
            return
        content = self.files.read(path, start, end)
        estimated_tokens = max(1, len(content) // 4)
        remaining = self.config.max_new_context_tokens - delta.token_cost
        if estimated_tokens > remaining:
            content = content[: max(0, remaining * 4)]
            estimated_tokens = max(0, len(content) // 4)
        if not content:
            return
        seen_regions.add(region_key)
        if path not in delta.new_files:
            delta.new_files.append(path)
        delta.new_code_regions.append(
            CodeRegion(path, start, end, content, str(action.get("reason", "")))
        )
        delta.token_cost += estimated_tokens
        target = self.root / path
        if target.suffix == ".py":
            for symbol, symbol_start, symbol_end in python_symbols(target):
                if symbol_end >= start and symbol_start <= end and history.is_new_symbol(symbol):
                    delta.new_symbols.append(symbol)
            delta.new_dependencies.extend(python_imports(target))
        normalized = path.lower()
        if "test" in normalized:
            delta.new_test_context.append(path)
