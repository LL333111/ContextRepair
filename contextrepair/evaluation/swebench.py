from __future__ import annotations

import json
import subprocess
from pathlib import Path


class SWEbenchAdapter:
    """Produces official prediction files and delegates scoring to SWE-bench's harness."""

    def predictions(self, results_root: Path, condition: str, output: Path, model_name: str) -> Path:
        records: list[dict] = []
        for result_path in results_root.glob(f"*/{condition}/final_result.json"):
            result = json.loads(result_path.read_text(encoding="utf-8"))
            patch_path = result_path.parent / "final.patch"
            records.append(
                {
                    "instance_id": result["instance_id"],
                    "model_name_or_path": model_name,
                    "model_patch": patch_path.read_text(encoding="utf-8"),
                }
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
        return output

    def run_official_evaluator(
        self,
        predictions_path: Path,
        *,
        dataset_name: str = "SWE-bench/SWE-bench_Verified",
        run_id: str,
        max_workers: int = 4,
        timeout: int = 1800,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            "python",
            "-m",
            "swebench.harness.run_evaluation",
            "--dataset_name",
            dataset_name,
            "--predictions_path",
            str(predictions_path),
            "--max_workers",
            str(max_workers),
            "--run_id",
            run_id,
        ]
        return subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )


def load_prepared_tasks(path: str | Path, instance_ids: set[str] | None = None) -> list[dict]:
    """Load task descriptors whose repositories/environments were prepared externally."""
    records: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if instance_ids is None or item["instance_id"] in instance_ids:
            required = {"instance_id", "issue", "repo_path", "test_command"}
            missing = required - item.keys()
            if missing:
                raise ValueError(f"Task {item.get('instance_id')} lacks: {sorted(missing)}")
            records.append(item)
    return records
