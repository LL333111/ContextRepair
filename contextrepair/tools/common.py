from __future__ import annotations

from pathlib import Path


class ToolError(RuntimeError):
    pass


def resolve_in_root(root: Path, relative: str) -> Path:
    if not relative or "\x00" in relative:
        raise ToolError("invalid empty path")
    root = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ToolError(f"path escapes repository root: {relative}") from exc
    return candidate


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    half = max(1, limit // 2)
    return value[:half] + f"\n... <{len(value) - limit} chars omitted> ...\n" + value[-half:]

