from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Sequence

import httpx
from pydantic import BaseModel, Field

from ogi.agent.tools import ToolDefinition
from ogi.config import settings


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LlmDecision(BaseModel):
    reasoning: str
    action_type: str
    tool_name: str | None = None
    tool_params: dict[str, Any] = Field(default_factory=dict)
    final_summary: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)


class LLMProvider(ABC):
    @abstractmethod
    async def decide(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
    ) -> LlmDecision:
        raise NotImplementedError


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1/chat/completions",
        retry_attempts: int = 3,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._retry_attempts = retry_attempts

    async def decide(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
    ) -> LlmDecision:
        if not self._api_key or not self._model:
            raise RuntimeError("LLM provider is not configured")

        tool_schema = [tool.model_dump(mode="json") for tool in tools]
        instruction = {
            "role": "system",
            "content": (
                "Return only JSON with fields: reasoning, action_type, tool_name, tool_params, final_summary. "
                "action_type must be 'tool_call' or 'finish'. tool_name must match one available tool. "
                "If finishing, set final_summary."
            ),
        }
        payload = {
            "model": self._model,
            "messages": [instruction, *messages, {"role": "system", "content": f"Tool schema: {json.dumps(tool_schema)}"}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(1, self._retry_attempts + 1):
                response = await client.post(self._base_url, headers=headers, json=payload)
                if response.status_code < 500 and response.status_code != 429:
                    response.raise_for_status()
                    data = response.json()
                    message = data["choices"][0]["message"]["content"]
                    parsed = json.loads(message)
                    usage = data.get("usage", {})
                    parsed["token_usage"] = {
                        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                        "completion_tokens": int(usage.get("completion_tokens", 0)),
                    }
                    return LlmDecision.model_validate(parsed)
                if attempt == self._retry_attempts:
                    response.raise_for_status()
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

        raise RuntimeError("LLM provider did not return a decision")


class ScriptedLLMProvider(LLMProvider):
    def __init__(self, decisions: Sequence[LlmDecision]) -> None:
        self._decisions = list(decisions)

    async def decide(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
    ) -> LlmDecision:
        if not self._decisions:
            raise RuntimeError("No scripted LLM decisions remain")
        return self._decisions.pop(0)


def build_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.strip().lower()
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleLLMProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            retry_attempts=settings.llm_retry_max_attempts,
        )
    raise RuntimeError(f"Unsupported LLM provider '{settings.llm_provider}'")
