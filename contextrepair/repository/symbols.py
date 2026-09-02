from __future__ import annotations

import ast
from pathlib import Path


def python_symbols(path: Path) -> list[tuple[str, int, int]]:
    """Return Python definitions without requiring a language server."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return []
    found: list[tuple[str, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            found.append((node.name, node.lineno, getattr(node, "end_lineno", node.lineno)))
    return sorted(found, key=lambda item: item[1])

