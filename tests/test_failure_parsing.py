import tempfile
import unittest
from pathlib import Path

from contextrepair.agent.base import parse_json_object
from contextrepair.recovery.failure_analyzer import (
    extract_failure_checklist,
    extract_repository_paths,
    extract_stack_trace,
    extract_test_evidence,
)
from contextrepair.types import FailureAnalysis


class FailureParsingTests(unittest.TestCase):
    def test_parses_fenced_json_and_defaults(self):
        parsed = parse_json_object(
            "```json\n{\"failure_summary\": \"wrong file\", \"failure_type\": \"wrong_localization\"}\n```"
        )
        analysis = FailureAnalysis.from_dict(parsed)
        self.assertEqual(analysis.failure_summary, "wrong file")
        self.assertEqual(analysis.candidate_files, [])

    def test_rejects_non_json(self):
        with self.assertRaises(ValueError):
            parse_json_object("I would inspect another module")

    def test_extracts_execution_trace(self):
        output = "setup output\nTraceback (most recent call last):\n  File 'x.py', line 1\nBoom"
        self.assertTrue(extract_stack_trace(output).startswith("Traceback"))

    def test_extracts_scored_test_region_without_setup_noise(self):
        output = (
            "very noisy setup\n"
            ">>>>> Start Test Output\nFAILED test_x\n"
            ">>>>> End Test Output\ncleanup noise"
        )
        evidence = extract_test_evidence(output)
        self.assertIn("FAILED test_x", evidence)
        self.assertNotIn("very noisy setup", evidence)
        self.assertNotIn("cleanup noise", evidence)

    def test_extracts_failure_checklist(self):
        output = (
            "FAIL: test_named (suite.Case)\n"
            "AssertionError: actual != expected\n"
            "FAIL: test_named (suite.Case)\n"
            "ERROR: test_unnamed (suite.Case)\n"
        )
        self.assertEqual(
            extract_failure_checklist(output),
            [
                "FAIL: test_named (suite.Case)",
                "AssertionError: actual != expected",
                "ERROR: test_unnamed (suite.Case)",
            ],
        )

    def test_extracts_repository_path_from_container_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "tests" / "test_views.py"
            target.parent.mkdir()
            target.write_text("pass\n", encoding="utf-8")
            output = '  File "/testbed/tests/test_views.py", line 10, in test_case\n'
            self.assertEqual(
                extract_repository_paths(output, root), ["tests/test_views.py"]
            )

    def test_normalizes_scalar_priority(self):
        analysis = FailureAnalysis.from_dict({"priority": "high"})
        self.assertEqual(analysis.priority, ["high"])


if __name__ == "__main__":
    unittest.main()
