from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Sequence

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ogi.agent.models import AgentRun
from ogi.agent.settings_models import AgentModelCatalog, AgentModelOption, AgentSettingsTestResult
from ogi.agent.tools import ToolDefinition
from ogi.config import settings
from ogi.store.api_key_store import ApiKeyStore


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


def _provider_error_message(provider: str, response: httpx.Response) -> str:
    body = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            if isinstance(payload.get("error"), dict):
                error = payload["error"]
                body = str(error.get("message") or error)
            else:
                body = json.dumps(payload)
        else:
            body = str(payload)
    except Exception:
        body = response.text.strip()

    body = body.strip()
    if len(body) > 500:
        body = f"{body[:500]}..."
    if body:
        return f"{provider} API error {response.status_code}: {body}"
    return f"{provider} API error {response.status_code}"


def _is_supported_openai_chat_model(model_id: str) -> bool:
    blocked_tokens = (
        "audio",
        "transcribe",
        "transcription",
        "tts",
        "realtime",
        "search",
        "image",
        "moderation",
        "embedding",
        "vision-preview",
        "instruct",
    )
    normalized = model_id.lower()
    if any(token in normalized for token in blocked_tokens):
        return False
    return (
        normalized.startswith("gpt-")
        or normalized.startswith("o1")
        or normalized.startswith("o3")
        or normalized.startswith("o4")
    )


class OpenAILLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
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
        system_prompt = (
            "You are the AI Investigator orchestrator for OpenGraph Intel. "
            "Return only JSON with fields: reasoning, action_type, tool_name, tool_params, final_summary. "
            "action_type must be 'tool_call' or 'finish'. tool_name must match one available tool. "
            "If finishing, set final_summary."
        )
        input_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
            {"role": "system", "content": f"Tool schema: {json.dumps(tool_schema)}"},
        ]

        client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            max_retries=0,
            timeout=60.0,
        )
        for attempt in range(1, self._retry_attempts + 1):
            try:
                response = await client.responses.create(
                    model=self._model,
                    input=input_messages,
                    text={"format": {"type": "json_object"}},
                )
                parsed = json.loads(response.output_text)
                usage = getattr(response, "usage", None)
                parsed["token_usage"] = {
                    "prompt_tokens": int(getattr(usage, "input_tokens", 0) or 0),
                    "completion_tokens": int(getattr(usage, "output_tokens", 0) or 0),
                }
                return LlmDecision.model_validate(parsed)
            except Exception as exc:
                status_code = getattr(exc, "status_code", None)
                if status_code is not None and status_code < 500 and status_code != 429:
                    message = getattr(exc, "message", "") or str(exc)
                    raise RuntimeError(f"OpenAI API error {status_code}: {message}") from exc
                if attempt == self._retry_attempts:
                    raise
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

        raise RuntimeError("LLM provider did not return a decision")


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
                    if response.is_error:
                        raise RuntimeError(_provider_error_message("OpenAI-compatible", response))
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


class AnthropicLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        retry_attempts: int = 3,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._retry_attempts = retry_attempts

    async def decide(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
    ) -> LlmDecision:
        instruction = (
            "Return only JSON with fields: reasoning, action_type, tool_name, tool_params, final_summary. "
            "action_type must be 'tool_call' or 'finish'. tool_name must match one available tool. "
            "If finishing, set final_summary."
        )
        payload = {
            "model": self._model,
            "max_tokens": 1024,
            "system": instruction,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Tool schema: {json.dumps([tool.model_dump(mode='json') for tool in tools])}\n\n"
                        f"Conversation: {json.dumps(messages)}"
                    ),
                }
            ],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(1, self._retry_attempts + 1):
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                )
                if response.status_code < 500 and response.status_code != 429:
                    if response.is_error:
                        raise RuntimeError(_provider_error_message("Anthropic", response))
                    data = response.json()
                    content_blocks = data.get("content", [])
                    text = "".join(
                        block.get("text", "")
                        for block in content_blocks
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                    parsed = json.loads(text)
                    usage = data.get("usage", {})
                    parsed["token_usage"] = {
                        "prompt_tokens": int(usage.get("input_tokens", 0)),
                        "completion_tokens": int(usage.get("output_tokens", 0)),
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


PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-3-5-sonnet-latest",
}

PROVIDER_RECOMMENDED_MODELS: dict[str, list[str]] = {
    "openai": ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "anthropic": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
}


def normalize_provider(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"anthropic", "claude"}:
        return "anthropic"
    return normalized


def provider_service_name(provider: str) -> str:
    normalized = normalize_provider(provider)
    if normalized == "anthropic":
        return "anthropic"
    return normalized


def _dedupe_model_options(items: Sequence[AgentModelOption]) -> list[AgentModelOption]:
    seen: set[str] = set()
    deduped: list[AgentModelOption] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        deduped.append(item)
    return deduped


async def _openai_list_models(api_key: str) -> list[AgentModelOption]:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("https://api.openai.com/v1/models", headers=headers)
        response.raise_for_status()
        data = response.json().get("data", [])
    models = [
        AgentModelOption(id=item["id"], label=item["id"], source="provider")
        for item in data
        if (
            isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item["id"]
            and _is_supported_openai_chat_model(item["id"])
        )
    ]
    return sorted(models, key=lambda item: item.id)


async def _openai_test_model(api_key: str, model: str) -> bool:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"https://api.openai.com/v1/models/{model}", headers=headers)
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True


async def _gemini_list_models(api_key: str) -> list[AgentModelOption]:
    headers = {"x-goog-api-key": api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("https://generativelanguage.googleapis.com/v1beta/models", headers=headers)
        response.raise_for_status()
        data = response.json().get("models", [])

    models: list[AgentModelOption] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        supported = item.get("supportedGenerationMethods") or []
        if "generateContent" not in supported:
            continue
        raw_name = item.get("name") or ""
        model_id = item.get("baseModelId") or raw_name.removeprefix("models/")
        display_name = item.get("displayName") or model_id
        if isinstance(model_id, str) and model_id:
            models.append(AgentModelOption(id=model_id, label=display_name, source="provider"))
    return sorted(_dedupe_model_options(models), key=lambda item: item.id)


async def _gemini_test_model(api_key: str, model: str) -> bool:
    headers = {"x-goog-api-key": api_key}
    normalized_model = model if model.startswith("models/") else f"models/{model}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://generativelanguage.googleapis.com/v1beta/{normalized_model}",
            headers=headers,
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True


async def _anthropic_list_models(api_key: str) -> list[AgentModelOption]:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("https://api.anthropic.com/v1/models", headers=headers)
        response.raise_for_status()
        data = response.json().get("data", [])
    models = [
        AgentModelOption(
            id=item["id"],
            label=item.get("display_name") or item["id"],
            source="provider",
        )
        for item in data
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    ]
    return sorted(models, key=lambda item: item.id)


async def _anthropic_test_model(api_key: str, model: str) -> bool:
    models = await _anthropic_list_models(api_key)
    return any(item.id == model for item in models)


async def list_provider_models(provider: str, api_key: str | None) -> AgentModelCatalog:
    normalized = normalize_provider(provider)
    default_model = PROVIDER_DEFAULT_MODELS.get(normalized, "")
    recommended = [
        AgentModelOption(id=model_id, label=model_id, source="recommended")
        for model_id in PROVIDER_RECOMMENDED_MODELS.get(normalized, [])
    ]
    if not api_key:
        return AgentModelCatalog(
            provider=normalized,
            default_model=default_model,
            recommended_models=recommended,
            available_models=recommended,
            has_api_key=False,
        )

    available: list[AgentModelOption]
    if normalized == "openai":
        available = await _openai_list_models(api_key)
    elif normalized == "gemini":
        available = await _gemini_list_models(api_key)
    elif normalized == "anthropic":
        available = await _anthropic_list_models(api_key)
    else:
        raise RuntimeError(f"Unsupported LLM provider '{provider}'")

    return AgentModelCatalog(
        provider=normalized,
        default_model=default_model,
        recommended_models=recommended,
        available_models=_dedupe_model_options([*available, *recommended]),
        has_api_key=True,
    )


async def test_provider_settings(provider: str, model: str, api_key: str | None) -> AgentSettingsTestResult:
    normalized = normalize_provider(provider)
    model_name = model.strip()
    if not api_key:
        return AgentSettingsTestResult(
            provider=normalized,
            model=model_name,
            success=False,
            has_api_key=False,
            model_found=False,
            message="No stored API key found for this provider.",
        )
    if not model_name:
        return AgentSettingsTestResult(
            provider=normalized,
            model=model_name,
            success=False,
            has_api_key=True,
            model_found=False,
            message="Model is required.",
        )

    try:
        catalog = await list_provider_models(normalized, api_key)
        if normalized == "openai":
            model_found = await _openai_test_model(api_key, model_name)
        elif normalized == "gemini":
            model_found = await _gemini_test_model(api_key, model_name)
        elif normalized == "anthropic":
            model_found = await _anthropic_test_model(api_key, model_name)
        else:
            raise RuntimeError(f"Unsupported LLM provider '{provider}'")
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        message = "Provider rejected the credentials or model test request."
        if status_code == 401:
            message = "Authentication failed for this provider API key."
        elif status_code == 403:
            message = "Provider access denied for this API key."
        elif status_code == 404:
            message = f"Model '{model_name}' was not found for this provider."
        return AgentSettingsTestResult(
            provider=normalized,
            model=model_name,
            success=False,
            has_api_key=True,
            model_found=False,
            message=message,
            available_models=catalog.available_models if "catalog" in locals() else [],
        )

    return AgentSettingsTestResult(
        provider=normalized,
        model=model_name,
        success=model_found,
        has_api_key=True,
        model_found=model_found,
        message=(
            f"Validated API key and model '{model_name}'."
            if model_found
            else f"API key is valid, but model '{model_name}' was not found."
        ),
        available_models=catalog.available_models,
    )


def build_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.strip().lower()
    if provider in {"openai", "openai-compatible"}:
        return OpenAILLMProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            retry_attempts=settings.llm_retry_max_attempts,
        )
    raise RuntimeError(f"Unsupported LLM provider '{settings.llm_provider}'")


async def build_llm_provider_for_run(
    *,
    session: AsyncSession,
    run: AgentRun,
) -> LLMProvider:
    provider = run.provider.strip().lower()
    model = run.model.strip()
    if not provider or not model:
        raise RuntimeError("AI Investigator run is missing provider or model")

    service_name = str((run.config or {}).get("provider_service") or provider).strip().lower()
    api_key = await ApiKeyStore(session).get_key(run.user_id, service_name)
    if not api_key:
        raise RuntimeError(f"Missing API key for AI provider '{service_name}'")

    if provider in {"openai", "openai-compatible"}:
        return OpenAILLMProvider(
            api_key=api_key,
            model=model,
            retry_attempts=settings.llm_retry_max_attempts,
        )

    if provider == "gemini":
        return OpenAICompatibleLLMProvider(
            api_key=api_key,
            model=model,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            retry_attempts=settings.llm_retry_max_attempts,
        )

    if provider in {"anthropic", "claude"}:
        return AnthropicLLMProvider(
            api_key=api_key,
            model=model,
            retry_attempts=settings.llm_retry_max_attempts,
        )

    raise RuntimeError(f"Unsupported LLM provider '{provider}'")
