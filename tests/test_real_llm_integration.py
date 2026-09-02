"""Opt-in integration proof. It intentionally never substitutes a mocked model."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from contextrepair.agent.controller import ExperimentController
from contextrepair.config import (
    AgentConfig,
    BudgetConfig,
    ExperimentConfig,
    ModelConfig,
    RecoveryConfig,
)
from contextrepair.types import Task


@unittest.skipUnless(os.getenv("RUN_REAL_LLM_INTEGRATION") == "1", "requires a real model API")
class RealLLMIntegrationTests(unittest.TestCase):
    def test_failure_then_recovery_on_real_repository(self):
        provider = os.environ.get("MODEL_PROVIDER", "openai")
        model_name = os.environ["MODEL_NAME"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "tiny-repo"
            repo.mkdir()
            (repo / "calculator.py").write_text(
                "def divide(a, b):\n    return a // b\n", encoding="utf-8"
            )
            (repo / "test_calculator.py").write_text(
                "import unittest\nfrom calculator import divide\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_fraction(self): self.assertEqual(divide(3, 2), 1.5)\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
                cwd=repo,
                check=True,
            )
            config = ExperimentConfig(
                condition="contextrepair",
                model=ModelConfig(
                    provider=provider,
                    name=model_name,
                    api_key_env=os.getenv("MODEL_API_KEY_ENV"),
                    base_url=os.getenv("MODEL_BASE_URL"),
                    input_cost_per_million=float(
                        os.getenv("MODEL_INPUT_COST_PER_MILLION", "0")
                    ),
                    output_cost_per_million=float(
                        os.getenv("MODEL_OUTPUT_COST_PER_MILLION", "0")
                    ),
                ),
                budget=BudgetConfig(max_total_tokens=30000, max_model_calls=20),
                recovery=RecoveryConfig(enabled=True),
                agent=AgentConfig(max_steps=6),
            )
            task = Task(
                "tiny-divide",
                "divide should perform true division and return fractional results",
                repo,
                f'"{sys.executable}" -m unittest -q',
            )
            result = ExperimentController(config, root / "results").run(task)
            print(
                "REAL_LLM_RESULT="
                + json.dumps(
                    {
                        key: result[key]
                        for key in (
                            "resolved",
                            "initial_resolved",
                            "recovery_attempted",
                            "recovered",
                            "model_calls",
                            "input_tokens",
                            "output_tokens",
                            "total_tokens",
                            "cost_usd",
                            "wall_seconds",
                        )
                    },
                    sort_keys=True,
                )
            )
            self.assertTrue(result["resolved"])
            self.assertTrue((root / "results" / "tiny-divide" / "contextrepair" / "final.patch").is_file())


if __name__ == "__main__":
    unittest.main()
