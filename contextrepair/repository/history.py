from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExplorationHistory:
    files: set[str] = field(default_factory=set)
    symbols: set[str] = field(default_factory=set)
    commands: list[str] = field(default_factory=list)
    searches: list[str] = field(default_factory=list)

    @classmethod
    def from_trajectory(cls, events: list[dict[str, Any]]) -> ExplorationHistory:
        history = cls()
        for event in events:
            history.files.update(str(path).replace("\\", "/") for path in event.get("files", []))
            history.symbols.update(str(symbol) for symbol in event.get("symbols", []))
            if event.get("action_type") == "shell":
                history.commands.append(str(event.get("content", "")))
            if event.get("action_type") == "search":
                history.searches.append(str(event.get("content", "")))
        return history

    def is_new_file(self, path: str) -> bool:
        return path.replace("\\", "/") not in self.files

    def is_new_symbol(self, symbol: str) -> bool:
        return symbol not in self.symbols

