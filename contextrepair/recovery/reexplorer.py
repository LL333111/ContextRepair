from __future__ import annotations

import json

from contextrepair.agent.base import parse_json_object
from contextrepair.agent.model_client import ModelClient
from contextrepair.repository.history import ExplorationHistory
from contextrepair.types import FailureAnalysis


class FailureConditionedReExplorer:
    """Uses failed execution evidence to decide where—not how—to investigate next."""

    def __init__(self, model: ModelClient):
        self.model = model

    def plan(
        self,
        *,
        issue: str,
        analysis: FailureAnalysis,
        history: ExplorationHistory,
        history_aware: bool = True,
        max_actions: int = 10,
    ) -> FailureAnalysis:
        history_payload = {
            "files_already_seen": sorted(history.files),
            "symbols_already_seen": sorted(history.symbols),
            "searches_already_run": history.searches,
        }
        if not history_aware:
            history_payload = {"history": "withheld for no-history-awareness ablation"}
        messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a failure-conditioned repository re-explorer. Select NEW repository "
                        "context that could test the failure hypotheses. Do not repair code. Return the "
                        "same JSON schema supplied in analysis. search_actions must be concrete JSON "
                        "objects of type read or search. A read has path, start_line, end_line, reason. "
                        "A search has query, path, optional glob, reason. Prioritize cross-file contracts, "
                        "callers, tests, and dependencies implicated by the evidence. Avoid seen context "
                        f"when history is available. Return at most {max_actions} actions."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "issue": issue,
                            "failure_analysis": analysis.to_dict(),
                            "exploration_history": history_payload,
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        response = self.model.generate(
            messages,
            max_tokens=2048,
            thinking=False,
            json_mode=True,
        )
        try:
            payload = parse_json_object(response.content)
        except (TypeError, ValueError):
            fallback = self.model.generate(
                messages,
                max_tokens=2048,
                thinking=False,
                json_mode=True,
            )
            payload = parse_json_object(fallback.content)
        embedded = payload.get("failure_analysis")
        refined_source = embedded if isinstance(embedded, dict) else payload
        refined = FailureAnalysis.from_dict(refined_source)

        # Re-exploration selects additional context; it must not erase a sound failure
        # diagnosis when a provider echoes the request in an envelope or omits fields.
        merged = FailureAnalysis.from_dict(analysis.to_dict())
        merged.candidate_files = _dedupe(
            analysis.candidate_files + refined.candidate_files
        )
        merged.candidate_symbols = _dedupe(
            analysis.candidate_symbols + refined.candidate_symbols
        )
        merged.priority = _dedupe(analysis.priority + refined.priority)

        raw_actions = payload.get("search_actions", refined.search_actions)
        normalized_actions: list[dict] = []
        if isinstance(raw_actions, list):
            for raw_action in raw_actions:
                if not isinstance(raw_action, dict):
                    continue
                action = raw_action.copy()
                if not action.get("type") and not action.get("action"):
                    if action.get("query"):
                        action["type"] = "search"
                    elif action.get("path"):
                        action["type"] = "read"
                if action.get("type") or action.get("action"):
                    normalized_actions.append(action)
        merged.search_actions = normalized_actions[:max_actions]
        return merged


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))
