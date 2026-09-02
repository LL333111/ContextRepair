from __future__ import annotations

import hashlib
import json
from pathlib import Path

PINNED_COMMIT = "08c82f46f3bec35596613fe88042e5a49128500f"
EXPECTED_SHA256 = "01e4893b41e2366637f8e9768d9155db82fb927bdfb8a02a5ed8422ce22db7be"
REPLACEMENTS = {
    'patch_file.write_text(pred["model_patch"] or "")': (
        'patch_file.write_text(pred["model_patch"] or "", newline="\\n")'
    ),
    "eval_file.write_text(_inject_asset_restore(test_spec.eval_script, restore_cmds))": (
        "eval_file.write_text("
        "_inject_asset_restore(test_spec.eval_script, restore_cmds), newline=\"\\n\""
        ")"
    ),
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main() -> None:
    target = Path(
        ".venv-swebench/Lib/site-packages/swebench/harness/run_evaluation.py"
    )
    marker = target.with_name("windows_newline_compat.json")
    original = target.read_bytes()
    original_hash = _sha256(original)
    content = original.decode("utf-8")

    if all(replacement in content for replacement in REPLACEMENTS.values()):
        print(marker.read_text(encoding="utf-8") if marker.is_file() else "already patched")
        return
    if original_hash != EXPECTED_SHA256:
        raise RuntimeError(
            f"Refusing to patch unexpected official harness file: {original_hash}"
        )
    for before, after in REPLACEMENTS.items():
        if content.count(before) != 1:
            raise RuntimeError(f"Expected exactly one compatibility target: {before}")
        content = content.replace(before, after)

    target.write_text(content, encoding="utf-8", newline="\n")
    payload = {
        "official_commit": PINNED_COMMIT,
        "original_sha256": original_hash,
        "patched_sha256": _sha256(target.read_bytes()),
        "change": "force LF for patch.diff and eval.sh copied into Linux containers",
    }
    marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
