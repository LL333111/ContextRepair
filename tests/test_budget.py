import unittest

from contextrepair.budget import BudgetExceeded, BudgetTracker
from contextrepair.config import BudgetConfig
from contextrepair.types import TokenUsage


class BudgetTests(unittest.TestCase):
    def test_accounts_calls_tokens_and_cost(self):
        tracker = BudgetTracker(BudgetConfig(max_total_tokens=20, max_model_calls=2))
        tracker.record(TokenUsage(3, 4, 0.25))
        snapshot = tracker.snapshot()
        self.assertEqual(snapshot.calls, 1)
        self.assertEqual(snapshot.input_tokens, 3)
        self.assertEqual(snapshot.output_tokens, 4)
        self.assertEqual(snapshot.cost_usd, 0.25)
        self.assertEqual(tracker.remaining_tokens(), 13)

    def test_enforces_call_limit(self):
        tracker = BudgetTracker(BudgetConfig(max_total_tokens=100, max_model_calls=1))
        tracker.record(TokenUsage(1, 1))
        with self.assertRaises(BudgetExceeded):
            tracker.ensure_available()


if __name__ == "__main__":
    unittest.main()

