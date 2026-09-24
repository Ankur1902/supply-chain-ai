"""
LLM abstraction layer. Everything in app/ai/* talks to this interface, never
directly to the Anthropic/Google SDKs — swapping providers means changing
this file only.

IMPORTANT (Windows-specific, see docs/decisions.md): this module is imported
BEFORE any ml library (xgboost/shap) anywhere in the app, because it's the
first thing app/main.py imports from app/ai. That's deliberate: chromadb
(imported by app/ai/rag.py, which this package also exposes) eagerly
instantiates an onnxruntime-backed embedding function at import time, and on
Windows, onnxruntime's bundled native runtime conflicts with xgboost's if
xgboost is imported into the process first. Importing chromadb-touching code
first avoids the crash. See app/main.py's import order and
docs/decisions.md ("Why import order matters on Windows").
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings

settings = get_settings()


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        ...


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system, messages, tools=None, max_tokens=1024) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools
            ]
        response = self._client.messages.create(**kwargs)

        text_parts = [b.text for b in response.content if b.type == "text"]
        tool_calls = [
            ToolCall(id=b.id, name=b.name, input=b.input) for b in response.content if b.type == "tool_use"
        ]
        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


class GoogleProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._model_name = model
        self._genai = genai

    def complete(self, system, messages, tools=None, max_tokens=1024) -> LLMResponse:
        model = self._genai.GenerativeModel(self._model_name, system_instruction=system)
        # Minimal role/content mapping; tool-calling for Gemini uses a
        # different schema than Anthropic's — the copilot primarily targets
        # Anthropic, this path covers basic non-tool chat/summarization only.
        history = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in messages]
        response = model.generate_content(history, generation_config={"max_output_tokens": max_tokens})
        return LLMResponse(text=response.text, tool_calls=[], stop_reason="end_turn")


class NullProvider(LLMProvider):
    """Used when LLM_PROVIDER=none (no API key configured). Keeps the rest of
    the app functional — deterministic analytics/tools still work, only the
    natural-language layer is disabled — instead of the whole AI feature
    surface crashing when no key is present (e.g. CI, first-run demo)."""

    def complete(self, system, messages, tools=None, max_tokens=1024) -> LLMResponse:
        return LLMResponse(
            text=(
                "The AI copilot's language model is not configured in this environment "
                "(LLM_PROVIDER=none or missing API key). Structured analytics tools still "
                "work through the REST API directly."
            ),
            stop_reason="end_turn",
        )


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
    if settings.llm_provider == "google" and settings.google_api_key:
        return GoogleProvider(settings.google_api_key, settings.google_model)
    return NullProvider()
