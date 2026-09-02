import json
import unittest
from types import SimpleNamespace

from contextrepair.recovery.reexplorer import FailureConditionedReExplorer
from contextrepair.repository.history import ExplorationHistory
from contextrepair.types import FailureAnalysis, ModelResponse


class ScriptedModel:
    def __init__(self, response: dict | list[str]):
        self.responses = iter(
            response if isinstance(response, list) else [json.dumps(response)]
        )
        self.config = SimpleNamespace(thinking_enabled=False)
        self.calls = []

    def generate(self, messages, **kwargs):
        del messages
        self.calls.append(kwargs)
        return ModelResponse(content=next(self.responses))


class ReExplorerTests(unittest.TestCase):
    def test_preserves_diagnosis_and_normalizes_enveloped_search_actions(self):
        analysis = FailureAnalysis(
            failure_summary="last group is skipped",
            failure_type="incomplete_fix",
            contradicted_assumptions=["only named groups fail"],
            missing_context_hypotheses=["unnamed groups use the same loop"],
            candidate_files=["module.py"],
            candidate_symbols=["replace_named"],
            search_actions=[],
            priority=["module.py"],
            rationale="official failures identify the boundary condition",
        )
        response = {
            "failure_analysis": analysis.to_dict(),
            "search_actions": [
                {
                    "query": "replace_unnamed",
                    "path": "module.py",
                    "reason": "inspect sibling implementation",
                }
            ],
        }
        refined = FailureConditionedReExplorer(ScriptedModel(response)).plan(
            issue="trailing group fails",
            analysis=analysis,
            history=ExplorationHistory(),
        )
        self.assertEqual(refined.failure_summary, "last group is skipped")
        self.assertEqual(refined.failure_type, "incomplete_fix")
        self.assertEqual(refined.search_actions[0]["type"], "search")
        self.assertEqual(refined.search_actions[0]["query"], "replace_unnamed")

    def test_retries_compact_non_thinking_plan_when_content_is_empty(self):
        response = {
            "failure_summary": "kept",
            "failure_type": "incomplete_fix",
            "search_actions": [],
        }
        model = ScriptedModel(["", json.dumps(response)])
        model.config.thinking_enabled = True
        analysis = FailureAnalysis.from_dict(response)
        refined = FailureConditionedReExplorer(model).plan(
            issue="failure",
            analysis=analysis,
            history=ExplorationHistory(),
        )
        self.assertEqual(refined.failure_summary, "kept")
        self.assertEqual(len(model.calls), 2)
        self.assertFalse(model.calls[0]["thinking"])
        self.assertFalse(model.calls[1]["thinking"])


if __name__ == "__main__":
    unittest.main()
