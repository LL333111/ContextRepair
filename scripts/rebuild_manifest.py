"""Rebuild or verify the release manifest from Git's staged file contents."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "MANIFEST.sha256"


def _git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "safe.directory=*", "-C", str(REPOSITORY_ROOT), *args]
    )


def _tracked_paths() -> list[str]:
    output = _git("ls-files", "-z")
    return sorted(
        path.decode("utf-8")
        for path in output.split(b"\0")
        if path and path != b"MANIFEST.sha256"
    )


def _index_bytes(path: str) -> bytes:
    return _git("show", f":{path}")


def rebuild() -> int:
    lines = [
        f"{hashlib.sha256(_index_bytes(path)).hexdigest()}  {path}\n"
        for path in _tracked_paths()
    ]
    MANIFEST_PATH.write_bytes("".join(lines).encode("utf-8"))
    print(f"Wrote {len(lines)} entries to {MANIFEST_PATH.name}")
    return 0


def verify() -> int:
    expected_paths = _tracked_paths()
    entries: dict[str, str] = {}
    malformed = 0
    for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        try:
            digest, path = line.split("  ", 1)
        except ValueError:
            malformed += 1
            continue
        entries[path] = digest

    errors: list[str] = []
    if malformed:
        errors.append(f"{malformed} malformed manifest line(s)")
    if sorted(entries) != expected_paths:
        errors.append("manifest paths do not match the Git index")
    for path in sorted(set(entries).intersection(expected_paths)):
        actual = hashlib.sha256(_index_bytes(path)).hexdigest()
        if actual != entries[path]:
            errors.append(f"hash mismatch: {path}")

    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Verified {len(entries)} manifest entries against the Git index")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify the existing manifest instead of rebuilding it",
    )
    args = parser.parse_args()
    return verify() if args.verify else rebuild()


if __name__ == "__main__":
    raise SystemExit(main())
