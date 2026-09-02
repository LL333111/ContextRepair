import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from contextrepair.agent.controller import ExperimentController
from contextrepair.agent.model_client import ModelClient
from contextrepair.budget import BudgetTracker
from contextrepair.config import (
    AgentConfig,
    BudgetConfig,
    ExperimentConfig,
    ModelConfig,
    RecoveryConfig,
)
from contextrepair.types import ModelResponse, Task, TokenUsage


class ScriptedUnitModel(ModelClient):
    """Unit-only orchestration fixture; the real integration test never uses this."""

    def __init__(self, responses, config, budget):
        super().__init__(config, budget)
        self.responses = iter(responses)

    def _generate(self, messages):
        return ModelResponse(next(self.responses), TokenUsage(10, 5), self.config.name)


class RecoveryOrchestrationTests(unittest.TestCase):
    def test_failed_attempt_builds_delta_and_recovers(self):
        analysis = {
            "failure_summary": "missed shared value contract",
            "failure_type": "missing_cross_file_dependency",
            "contradicted_assumptions": [],
            "missing_context_hypotheses": ["helper documents the expected value"],
            "candidate_files": ["helper.py"],
            "candidate_symbols": ["expected"],
            "search_actions": [
                {"type": "read", "path": "helper.py", "start_line": 1, "end_line": 20}
            ],
            "priority": ["helper.py"],
            "rationale": "test failure contradicts current behavior",
        }
        responses = [
            json.dumps({"action": "final", "summary": "no change", "hypothesis": "already correct"}),
            json.dumps(analysis),
            json.dumps(analysis),
            json.dumps(
                {
                    "action": "write",
                    "path": "target.py",
                    "content": "def value():\n    return 2  # aligned with shared contract\n",
                    "hypothesis": "implementation disagrees with the shared contract",
                }
            ),
            json.dumps({"action": "final", "summary": "aligned implementation"}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            (repo / "target.py").write_text("def value():\n    return 1\n", encoding="utf-8")
            (repo / "helper.py").write_text("def expected():\n    return 2\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-qm",
                    "base",
                ],
                cwd=repo,
                check=True,
            )
            budget_config = BudgetConfig(max_total_tokens=1000, max_model_calls=10, max_attempts=2)
            model_config = ModelConfig(provider="ollama", name="unit-script")
            config = ExperimentConfig(
                condition="contextrepair",
                model=model_config,
                budget=budget_config,
                recovery=RecoveryConfig(enabled=True),
                agent=AgentConfig(max_steps=2),
            )
            model = ScriptedUnitModel(responses, model_config, BudgetTracker(budget_config))
            command = f'"{sys.executable}" -c "import target; assert target.value() == 2"'
            result = ExperimentController(config, root / "results", model=model).run(
                Task("orchestration", "value must follow the shared contract", repo, command)
            )
            task_dir = root / "results" / "orchestration" / "contextrepair"
            self.assertFalse(result["initial_resolved"])
            self.assertTrue(result["recovered"], result)
            delta = json.loads((task_dir / "context_delta.json").read_text(encoding="utf-8"))
            self.assertEqual(delta["new_files"], ["helper.py"])
            self.assertIn("return 2", (task_dir / "final.patch").read_text(encoding="utf-8"))
            calls = json.loads((task_dir / "model_calls.json").read_text(encoding="utf-8"))
            self.assertEqual(len(calls["calls"]), 5)


if __name__ == "__main__":
    unittest.main()
