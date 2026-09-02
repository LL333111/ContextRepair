from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contextrepair.budget import BudgetTracker
from contextrepair.config import ModelConfig
from contextrepair.run_state import atomic_write_json
from contextrepair.types import ModelResponse, TokenUsage


class ModelError(RuntimeError):
    pass


class ModelClient(ABC):
    """Provider-neutral model interface. Implementations must report token usage."""

    def __init__(self, config: ModelConfig, budget: BudgetTracker):
        self.config = config
        self.budget = budget
        self.call_log: list[dict[str, Any]] = []
        self.usage_journal_path: Path | None = None
        self._generation_max_tokens = config.max_tokens
        self._generation_thinking: bool | None = None
        self._generation_json_mode = False

    def set_usage_journal_path(self, path: str | Path) -> None:
        self.usage_journal_path = Path(path)

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        thinking: bool | None = None,
        json_mode: bool = False,
    ) -> ModelResponse:
        self.budget.ensure_available()
        requested_max_tokens = max_tokens or self.config.max_tokens
        self._generation_max_tokens = requested_max_tokens
        self._generation_thinking = thinking
        self._generation_json_mode = json_mode
        try:
            response = self._generate(messages)
        finally:
            self._generation_max_tokens = self.config.max_tokens
            self._generation_thinking = None
            self._generation_json_mode = False
        if response.usage.input_tokens == 0 and response.usage.output_tokens == 0:
            # Some local OpenAI-compatible servers omit usage. Never record a silent zero.
            response.usage.input_tokens = max(
                1, sum(len(message.get("content", "")) for message in messages) // 4
            )
            response.usage.output_tokens = max(1, len(response.content) // 4)
            response.usage.estimated = True
        response.usage.cost_usd = self._cost(response.usage)
        self.call_log.append(
            {
                "call": len(self.call_log) + 1,
                "timestamp": datetime.now(UTC).isoformat(),
                "model": response.model or self.config.name,
                "generation": {
                    "max_tokens": requested_max_tokens,
                    "thinking": thinking,
                    "json_mode": json_mode,
                },
                "messages": [message.copy() for message in messages],
                "response": response.content,
                "token_usage": response.usage.to_dict(),
            }
        )
        self._flush_usage_journal()
        self.budget.record(response.usage)
        return response

    def _flush_usage_journal(self) -> None:
        if self.usage_journal_path is None:
            return
        atomic_write_json(
            self.usage_journal_path,
            {
                "calls": [
                    {
                        "call": call["call"],
                        "timestamp": call["timestamp"],
                        "model": call["model"],
                        "token_usage": call["token_usage"],
                    }
                    for call in self.call_log
                ]
            },
        )

    @abstractmethod
    def _generate(self, messages: list[dict[str, str]]) -> ModelResponse:
        raise NotImplementedError

    def _cost(self, usage: TokenUsage) -> float:
        return (
            usage.input_tokens * self.config.input_cost_per_million
            + usage.output_tokens * self.config.output_cost_per_million
        ) / 1_000_000

    def _max_generation_tokens(self) -> int:
        return min(self._generation_max_tokens, self.budget.remaining_tokens())

    def _api_key(self, default_env: str) -> str:
        env_name = self.config.api_key_env or default_env
        value = os.getenv(env_name)
        if not value:
            raise ModelError(f"Missing API key environment variable: {env_name}")
        return value

    @staticmethod
    def _post(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                retryable = exc.code == 429 or exc.code >= 500
                if not retryable or attempt == 3:
                    raise ModelError(
                        f"Provider returned HTTP {exc.code}: {body[:2000]}"
                    ) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == 3:
                    raise ModelError(f"Provider request failed: {exc}") from exc
            time.sleep(min(0.5 * (2**attempt), 4.0))
        raise AssertionError("provider retry loop terminated unexpectedly")


class OpenAICompatibleClient(ModelClient):
    def _generate(self, messages: list[dict[str, str]]) -> ModelResponse:
        base_url = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        key = self._api_key("OPENAI_API_KEY")
        payload: dict[str, Any] = {
            "model": self.config.name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self._max_generation_tokens(),
        }
        if self._generation_json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self._generation_thinking is not None and (
            "deepseek" in base_url.lower()
            or self.config.name.lower().startswith("deepseek-")
        ):
            payload["thinking"] = {
                "type": "enabled" if self._generation_thinking else "disabled"
            }
        raw = self._post(
            f"{base_url}/chat/completions",
            {"Authorization": f"Bearer {key}"},
            payload,
        )
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError(f"Malformed OpenAI-compatible response: {raw}") from exc
        usage = raw.get("usage", {})
        return ModelResponse(
            content=content or "",
            model=str(raw.get("model", self.config.name)),
            usage=TokenUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            ),
            raw=raw,
        )


class AnthropicClient(ModelClient):
    def _generate(self, messages: list[dict[str, str]]) -> ModelResponse:
        key = self._api_key("ANTHROPIC_API_KEY")
        system_parts = [message["content"] for message in messages if message["role"] == "system"]
        conversation = [message for message in messages if message["role"] != "system"]
        raw = self._post(
            (self.config.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            {
                "model": self.config.name,
                "system": "\n\n".join(system_parts),
                "messages": conversation,
                "temperature": self.config.temperature,
                "max_tokens": self._max_generation_tokens(),
            },
        )
        blocks = raw.get("content", [])
        content = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        usage = raw.get("usage", {})
        return ModelResponse(
            content=content,
            model=str(raw.get("model", self.config.name)),
            usage=TokenUsage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            ),
            raw=raw,
        )


class OllamaClient(ModelClient):
    """Local OpenAI-compatible Ollama endpoint; no secret is required."""

    def _api_key(self, default_env: str) -> str:
        return "ollama"

    def _generate(self, messages: list[dict[str, str]]) -> ModelResponse:
        base_url = (self.config.base_url or "http://localhost:11434/v1").rstrip("/")
        raw = self._post(
            f"{base_url}/chat/completions",
            {"Authorization": "Bearer ollama"},
            {
                "model": self.config.name,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self._max_generation_tokens(),
            },
        )
        content = raw["choices"][0]["message"]["content"]
        usage = raw.get("usage", {})
        return ModelResponse(
            content=content,
            model=str(raw.get("model", self.config.name)),
            usage=TokenUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            ),
            raw=raw,
        )


def create_model_client(config: ModelConfig, budget: BudgetTracker) -> ModelClient:
    provider = config.provider.lower()
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleClient(config, budget)
    if provider == "anthropic":
        return AnthropicClient(config, budget)
    if provider == "ollama":
        return OllamaClient(config, budget)
    raise ValueError(f"Unsupported model provider: {config.provider}")
