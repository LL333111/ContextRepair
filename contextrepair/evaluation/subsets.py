from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime
from pathlib import Path


class LockedSubsetError(RuntimeError):
    pass


def lock_subset(
    path: str | Path,
    instance_ids: list[str],
    *,
    size: int,
    seed: int,
    source: str,
) -> dict:
    target = Path(path)
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing.get("locked"):
            raise LockedSubsetError(f"Subset is already locked: {target}")
    unique_ids = sorted(set(instance_ids))
    if size < 1 or size > len(unique_ids):
        raise ValueError(f"size must be between 1 and {len(unique_ids)}")
    selected = sorted(random.Random(seed).sample(unique_ids, size))
    digest = hashlib.sha256("\n".join(selected).encode("utf-8")).hexdigest()
    payload = {
        "benchmark": source,
        "locked": True,
        "seed": seed,
        "size": size,
        "instance_ids": selected,
        "sha256": digest,
        "locked_at": datetime.now(UTC).isoformat(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_locked_subset(path: str | Path) -> list[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not payload.get("locked"):
        raise LockedSubsetError(f"Subset has not been locked: {path}")
    ids = list(payload.get("instance_ids", []))
    digest = hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()
    if digest != payload.get("sha256"):
        raise LockedSubsetError(f"Subset checksum does not match: {path}")
    return ids

