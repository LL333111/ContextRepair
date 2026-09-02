import tempfile
import unittest
from pathlib import Path

from contextrepair.logging import TrajectoryLogger


class TrajectoryTests(unittest.TestCase):
    def test_round_trip_and_monotonic_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.json"
            logger = TrajectoryLogger(path, "initial")
            logger.add("agent", "search", "query", files=["a.py"])
            logger.add("tool", "read", "content", symbols=["Widget"])
            events = TrajectoryLogger.load(path)
            self.assertEqual([event["step"] for event in events], [1, 2])
            self.assertEqual(events[0]["files"], ["a.py"])
            self.assertEqual(events[1]["symbols"], ["Widget"])
            self.assertEqual(events[0]["phase"], "initial")


if __name__ == "__main__":
    unittest.main()

