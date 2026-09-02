import tempfile
import unittest
from pathlib import Path

from contextrepair.config import RecoveryConfig
from contextrepair.recovery.context_delta import ContextDeltaBuilder
from contextrepair.repository.history import ExplorationHistory
from contextrepair.types import FailureAnalysis


def analysis(candidate_files):
    return FailureAnalysis(
        failure_summary="missed contract",
        failure_type="missing_cross_file_dependency",
        contradicted_assumptions=[],
        missing_context_hypotheses=[],
        candidate_files=candidate_files,
        candidate_symbols=[],
        search_actions=[],
        priority=[],
        rationale="",
    )


class ContextDeltaTests(unittest.TestCase):
    def test_filters_seen_files_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "seen.py").write_text("def old():\n    pass\n", encoding="utf-8")
            (root / "new.py").write_text("import json\n\ndef fresh():\n    return json.dumps({})\n", encoding="utf-8")
            history = ExplorationHistory(files={"seen.py"}, symbols={"old"})
            delta = ContextDeltaBuilder(root, RecoveryConfig()).build(
                analysis(["seen.py", "new.py", "new.py"]), history
            )
            self.assertEqual(delta.new_files, ["new.py"])
            self.assertEqual(len(delta.new_code_regions), 1)
            self.assertEqual(len(delta.anchor_code_regions), 1)
            self.assertEqual(delta.anchor_code_regions[0].path, "seen.py")
            self.assertIn("def old", delta.anchor_code_regions[0].content)
            self.assertGreater(delta.anchor_token_cost, 0)
            self.assertIn("fresh", delta.new_symbols)
            self.assertIn("json", delta.new_dependencies)

    def test_respects_context_token_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "large.txt").write_text("x" * 1000, encoding="utf-8")
            config = RecoveryConfig(max_new_context_tokens=10)
            delta = ContextDeltaBuilder(root, config).build(
                analysis(["large.txt"]), ExplorationHistory()
            )
            self.assertLessEqual(delta.token_cost, 10)


if __name__ == "__main__":
    unittest.main()
