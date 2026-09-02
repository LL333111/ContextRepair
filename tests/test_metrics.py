import unittest

from contextrepair.evaluation.metrics import aggregate_results
from contextrepair.evaluation.sweexplore import localization_metrics, mechanism_comparison


class MetricTests(unittest.TestCase):
    def test_result_aggregation(self):
        summary = aggregate_results(
            [
                {"resolved": True, "initial_resolved": True, "total_tokens": 10, "cost_usd": 1},
                {
                    "resolved": True,
                    "initial_resolved": False,
                    "recovered": True,
                    "total_tokens": 30,
                    "cost_usd": 2,
                },
                {"resolved": False, "initial_resolved": False, "total_tokens": 20, "cost_usd": 3},
            ]
        )
        self.assertAlmostEqual(summary["resolved_pct"], 200 / 3)
        self.assertEqual(summary["recovery_pct"], 50.0)
        self.assertEqual(summary["avg_total_tokens"], 20.0)
        self.assertEqual(summary["cost_per_resolved_usd"], 3.0)

    def test_localization_metrics(self):
        metrics = localization_metrics(
            {"a.py", "b.py"},
            {"a.py": {10, 11}, "b.py": {20}},
            {"a.py"},
            [("a.py", 9, 10)],
            1000,
        )
        self.assertEqual(metrics["relevant_file_recall"], 0.5)
        self.assertAlmostEqual(metrics["relevant_line_coverage"], 1 / 3)
        self.assertEqual(metrics["relevant_context_per_1k_tokens"], 2.0)

    def test_mechanism_comparison_counts_only_new_relevant_files(self):
        comparison = mechanism_comparison(
            relevant_files={"a.py", "b.py"},
            relevant_lines={"a.py": {5}, "b.py": {10}},
            initial_trajectory=[
                {
                    "action_type": "read",
                    "files": ["a.py"],
                    "metadata": {"start_line": 1, "end_line": 8},
                    "content": "a" * 400,
                }
            ],
            context_delta={
                "new_files": ["b.py"],
                "new_code_regions": [{"path": "b.py", "start_line": 8, "end_line": 12}],
                "token_cost": 20,
            },
        )
        self.assertEqual(comparison["initial"]["relevant_file_recall"], 0.5)
        self.assertEqual(comparison["after_reexploration"]["relevant_file_recall"], 1.0)
        self.assertEqual(comparison["new_relevant_files"], ["b.py"])


if __name__ == "__main__":
    unittest.main()
