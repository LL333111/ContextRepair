import tempfile
import unittest
from pathlib import Path

from contextrepair.config import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_nested_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                "condition: retry\nmodel:\n  provider: ollama\n  name: qwen\n"
                "budget:\n  max_total_tokens: 123\n  max_attempts: 2\n"
                "recovery:\n  enabled: false\n",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.condition, "retry")
            self.assertEqual(config.model.provider, "ollama")
            self.assertEqual(config.budget.max_total_tokens, 123)
            self.assertFalse(config.recovery.enabled)

    def test_rejects_unknown_condition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("condition: magic\nmodel:\n  provider: ollama\n  name: x\n")
            with self.assertRaises(ValueError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
