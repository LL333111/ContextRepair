import json
import tempfile
import unittest
from pathlib import Path

from contextrepair.evaluation.subsets import LockedSubsetError, load_locked_subset, lock_subset


class SubsetTests(unittest.TestCase):
    def test_deterministic_lock_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subset.json"
            payload = lock_subset(
                path, [f"task-{index}" for index in range(10)], size=4, seed=7, source="test"
            )
            self.assertEqual(load_locked_subset(path), payload["instance_ids"])
            with self.assertRaises(LockedSubsetError):
                lock_subset(path, ["x"], size=1, seed=0, source="test")

    def test_detects_manual_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subset.json"
            lock_subset(path, ["a", "b"], size=1, seed=0, source="test")
            value = json.loads(path.read_text())
            value["instance_ids"] = ["tampered"]
            path.write_text(json.dumps(value))
            with self.assertRaises(LockedSubsetError):
                load_locked_subset(path)


if __name__ == "__main__":
    unittest.main()

