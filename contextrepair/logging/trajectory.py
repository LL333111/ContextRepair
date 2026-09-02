from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contextrepair.run_state import atomic_write_json


@dataclass(slots=True)
class TrajectoryEvent:
    step: int
    phase: str
    role: str
    action_type: str
    content: str
    files: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    token_usage: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class TrajectoryLogger:
    def __init__(self, path: str | Path, phase: str):
        self.path = Path(path)
        self.phase = phase
        self.events: list[TrajectoryEvent] = []

    def add(
        self,
        role: str,
        action_type: str,
        content: str,
        *,
        files: list[str] | None = None,
        symbols: list[str] | None = None,
        token_usage: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TrajectoryEvent:
        event = TrajectoryEvent(
            step=len(self.events) + 1,
            phase=self.phase,
            role=role,
            action_type=action_type,
            content=content,
            files=files or [],
            symbols=symbols or [],
            token_usage=token_usage or {},
            metadata=metadata or {},
        )
        self.events.append(event)
        self.flush()
        return event

    def flush(self) -> None:
        atomic_write_json(self.path, [asdict(event) for event in self.events])

    @classmethod
    def load(cls, path: str | Path) -> list[dict[str, Any]]:
        return json.loads(Path(path).read_text(encoding="utf-8"))
