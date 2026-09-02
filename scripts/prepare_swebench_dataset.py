from __future__ import annotations

import json
from pathlib import Path

from datasets import load_dataset

from contextrepair.run_state import atomic_write_text

DATASET_NAME = "SWE-bench/SWE-bench_Verified"


def main() -> None:
    dataset = load_dataset(DATASET_NAME, split="test")
    records = sorted((dict(row) for row in dataset), key=lambda row: row["instance_id"])
    instance_ids = [str(row["instance_id"]) for row in records]
    if len(instance_ids) != 500 or len(instance_ids) != len(set(instance_ids)):
        raise RuntimeError(
            f"Expected 500 unique SWE-bench Verified instances, got {len(instance_ids)}"
        )

    universe = Path("benchmark_subsets/verified_ids.txt")
    cache = Path(".cache/swebench_verified.jsonl")
    atomic_write_text(universe, "\n".join(instance_ids) + "\n")
    atomic_write_text(
        cache,
        "\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n",
    )
    repositories = sorted({str(row["repo"]) for row in records})
    print(
        json.dumps(
            {
                "dataset": DATASET_NAME,
                "instances": len(instance_ids),
                "repositories": len(repositories),
                "universe": str(universe),
                "cache": str(cache),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
