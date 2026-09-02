import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from contextrepair.cli import benchmark_command
from contextrepair.evaluation.subsets import lock_subset
from contextrepair.run_state import (
    archive_partial_task,
    consumed_cost_usd,
    task_condition_dir,
)


class RunStateTests(unittest.TestCase):
    def test_archives_partial_and_accounts_interrupted_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            partial = task_condition_dir(root, "task-a", "single")
            partial.mkdir(parents=True)
            (partial / "model_usage.partial.json").write_text(
                json.dumps(
                    {"calls": [{"token_usage": {"cost_usd": 0.25}}]}
                ),
                encoding="utf-8",
            )
            archive = archive_partial_task(root, "task-a", "single")
            self.assertIsNotNone(archive)
            self.assertFalse(partial.exists())
            self.assertTrue(archive.is_dir())
            total, completed, interrupted = consumed_cost_usd(root)
            self.assertEqual(total, 0.25)
            self.assertEqual(completed, 0.0)
            self.assertEqual(interrupted, 0.25)

    def test_benchmark_resumes_by_skipping_completed_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subset = root / "subset.json"
            lock_subset(subset, ["a", "b"], size=2, seed=0, source="test")
            tasks = root / "tasks.jsonl"
            tasks.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "instance_id": item,
                            "issue": "issue",
                            "repo_path": str(root),
                            "test_command": "true",
                        }
                    )
                    for item in ("a", "b")
                ),
                encoding="utf-8",
            )
            config = root / "single.yaml"
            config.write_text(
                "condition: single\n"
                "model:\n  provider: ollama\n  name: test\n"
                "budget:\n  max_attempts: 1\n"
                "recovery:\n  enabled: false\n",
                encoding="utf-8",
            )
            results = root / "results"
            completed_dir = task_condition_dir(results, "a", "single")
            completed_dir.mkdir(parents=True)
            completed = {
                "instance_id": "a",
                "condition": "single",
                "resolved": True,
                "initial_resolved": True,
                "cost_usd": 0.1,
            }
            (completed_dir / "final_result.json").write_text(
                json.dumps(completed), encoding="utf-8"
            )

            calls = []

            class FakeController:
                def __init__(self, _config, _results):
                    pass

                def run(self, task):
                    calls.append(task.instance_id)
                    task_dir = task_condition_dir(results, task.instance_id, "single")
                    task_dir.mkdir(parents=True, exist_ok=True)
                    value = {
                        "instance_id": task.instance_id,
                        "condition": "single",
                        "resolved": False,
                        "initial_resolved": False,
                        "cost_usd": 0.2,
                    }
                    (task_dir / "final_result.json").write_text(
                        json.dumps(value), encoding="utf-8"
                    )
                    return value

            args = Namespace(
                config=str(config),
                condition="single",
                subset=str(subset),
                tasks_file=str(tasks),
                results=str(results),
                max_total_cost_usd=10.0,
                task_retries=0,
            )
            with patch("contextrepair.cli.ExperimentController", FakeController):
                exit_code = benchmark_command(args)
            self.assertEqual(exit_code, 0)
            self.assertEqual(calls, ["b"])
            summary = json.loads((results / "summary_single.json").read_text())
            self.assertEqual(summary["tasks"], 2)


if __name__ == "__main__":
    unittest.main()
