import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from contextrepair.agent.base import CodingAgent
from contextrepair.agent.model_client import ModelClient
from contextrepair.budget import BudgetTracker
from contextrepair.config import AgentConfig, BudgetConfig, ModelConfig
from contextrepair.logging import TrajectoryLogger
from contextrepair.types import ModelResponse, TokenUsage


class ScriptedModel(ModelClient):
    def __init__(self, responses: list[str]):
        config = ModelConfig(provider="ollama", name="scripted", max_tokens=512)
        super().__init__(config, BudgetTracker(BudgetConfig(max_total_tokens=10_000)))
        self.responses = iter(responses)

    def _generate(self, messages: list[dict[str, str]]) -> ModelResponse:
        del messages
        return ModelResponse(
            content=next(self.responses),
            model="scripted",
            usage=TokenUsage(input_tokens=5, output_tokens=5),
        )


class AgentLoopTests(unittest.TestCase):
    def test_repairs_invalid_json_without_spending_an_action_step(self):
        responses = [
            "",
            json.dumps(
                {
                    "action": "replace",
                    "path": "target.py",
                    "old": "return 1",
                    "new": "return 2",
                }
            ),
            json.dumps({"action": "final", "summary": "fixed"}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.py").write_text(
                "def value():\n    return 1\n", encoding="utf-8"
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "target.py"], cwd=root, check=True)
            trajectory = TrajectoryLogger(root / "trajectory.json", "recovery")
            model = ScriptedModel(responses)
            agent = CodingAgent(
                root,
                model,
                AgentConfig(max_steps=2, max_json_repairs=1),
                trajectory,
                "recovery",
            )
            command = f'"{sys.executable}" -c "import target; assert target.value() == 2"'
            outcome = agent.run("value must be two", command)
            self.assertTrue(outcome.success)
            self.assertEqual(len(model.call_log), 3)
            events = json.loads((root / "trajectory.json").read_text(encoding="utf-8"))
            self.assertTrue(any(event["action_type"] == "json_repair" for event in events))

    def test_failed_locked_edit_allows_one_exact_correction_read(self):
        diagnostics = [
            {"action": "read", "path": "target.py", "start_line": 1, "end_line": end}
            for end in range(1, 6)
        ]
        responses = [
            *(json.dumps(action) for action in diagnostics),
            json.dumps(
                {
                    "action": "replace",
                    "path": "target.py",
                    "old": "return missing",
                    "new": "return 2",
                }
            ),
            json.dumps(
                {"action": "read", "path": "target.py", "start_line": 1, "end_line": 6}
            ),
            json.dumps(
                {
                    "action": "replace",
                    "path": "target.py",
                    "old": "return 1",
                    "new": "return 2",
                }
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.py").write_text(
                "def value():\n    return 1\n", encoding="utf-8"
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "target.py"], cwd=root, check=True)
            trajectory = TrajectoryLogger(root / "trajectory.json", "recovery")
            agent = CodingAgent(
                root,
                ScriptedModel(responses),
                AgentConfig(max_steps=8),
                trajectory,
                "recovery",
            )
            command = f'"{sys.executable}" -c "import target; assert target.value() == 2"'
            outcome = agent.run("value must be two", command)
            self.assertTrue(outcome.success)
            events = json.loads((root / "trajectory.json").read_text(encoding="utf-8"))
            observations = [event["content"] for event in events if event["role"] == "tool"]
            self.assertTrue(any("CORRECTION READ USED" in item for item in observations))

    def test_rejects_final_after_only_noop_edit(self):
        responses = [
            json.dumps(
                {
                    "action": "replace",
                    "path": "target.py",
                    "old": "return 1",
                    "new": "return 1",
                }
            ),
            json.dumps({"action": "final", "summary": "done"}),
            json.dumps(
                {
                    "action": "replace",
                    "path": "target.py",
                    "old": "return 1",
                    "new": "return 2",
                }
            ),
            json.dumps({"action": "final", "summary": "fixed"}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.py").write_text(
                "def value():\n    return 1\n", encoding="utf-8"
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "target.py"], cwd=root, check=True)
            trajectory = TrajectoryLogger(root / "trajectory.json", "initial")
            agent = CodingAgent(
                root,
                ScriptedModel(responses),
                AgentConfig(max_steps=4),
                trajectory,
                "initial",
            )
            command = f'"{sys.executable}" -c "import target; assert target.value() == 2"'
            outcome = agent.run("value must be two", command)
            self.assertTrue(outcome.success)
            events = json.loads((root / "trajectory.json").read_text(encoding="utf-8"))
            observations = [event["content"] for event in events if event["role"] == "tool"]
            self.assertTrue(any("every edit attempt was a no-op" in item for item in observations))

    def test_blocks_duplicate_diagnostic_and_accepts_replace(self):
        diagnostic = {"action": "shell", "command": "python -c \"print(1)\""}
        responses = [
            json.dumps(diagnostic),
            json.dumps(diagnostic),
            json.dumps(
                {
                    "action": "replace",
                    "path": "target.py",
                    "old": "return 1",
                    "new": "return 2",
                }
            ),
            json.dumps({"action": "final", "summary": "fixed"}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.py").write_text(
                "def value():\n    return 1\n", encoding="utf-8"
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "target.py"], cwd=root, check=True)
            trajectory = TrajectoryLogger(root / "trajectory.json", "initial")
            agent = CodingAgent(
                root,
                ScriptedModel(responses),
                AgentConfig(max_steps=4),
                trajectory,
                "initial",
            )
            command = f'"{sys.executable}" -c "import target; assert target.value() == 2"'
            outcome = agent.run("value must be two", command)
            self.assertTrue(outcome.success)
            events = json.loads((root / "trajectory.json").read_text(encoding="utf-8"))
            observations = [event["content"] for event in events if event["role"] == "tool"]
            self.assertTrue(any("exact duplicate action blocked" in item for item in observations))
            self.assertIn("return 2", (root / "target.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
