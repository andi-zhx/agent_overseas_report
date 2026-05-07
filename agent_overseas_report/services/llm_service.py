"""Reusable OpenAI-compatible LLM service backed by DeepSeek.

DeepSeek exposes an OpenAI-compatible Chat Completions API, so this service
keeps provider-specific configuration in one place while presenting a small
interface that CrewAI tasks/tools can reuse or replace later.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT_SECONDS = 60.0


class LLMServiceError(RuntimeError):
    """Base exception for LLM service failures."""


class LLMConfigurationError(LLMServiceError):
    """Raised when required LLM configuration is missing or invalid."""


class LLMTimeoutError(LLMServiceError):
    """Raised when the model provider request times out."""


class LLMEmptyResponseError(LLMServiceError):
    """Raised when the model provider returns no usable content."""


class LLMJsonParseError(LLMServiceError):
    """Raised when the model output cannot be parsed as JSON."""


class LLMProviderError(LLMServiceError):
    """Raised for provider-side or SDK errors."""


@dataclass(frozen=True)
class DeepSeekLLMConfig:
    """Configuration for DeepSeek's OpenAI-compatible API."""

    api_key: str
    model: str = DEFAULT_DEEPSEEK_MODEL
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "DeepSeekLLMConfig":
        """Build configuration from environment variables."""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise LLMConfigurationError("Missing required environment variable: DEEPSEEK_API_KEY")

        model = os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
        base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL)
        timeout_raw = os.getenv("DEEPSEEK_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))

        try:
            timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise LLMConfigurationError("DEEPSEEK_TIMEOUT_SECONDS must be a number") from exc

        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )


class DeepSeekLLMService:
    """Small reusable service for text and JSON generation via DeepSeek."""

    def __init__(
        self,
        config: DeepSeekLLMConfig | None = None,
        client: Any | None = None,
    ) -> None:
        self.config = config or DeepSeekLLMConfig.from_env()
        if client is None:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
            )
        else:
            self.client = client

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate plain text for a prompt.

        Prompt content is intentionally not written to logs; only prompt length
        and model metadata are logged to reduce the risk of leaking sensitive
        business context.
        """
        logger.info(
            "Calling LLM text generation: provider=deepseek model=%s prompt_chars=%s has_system_prompt=%s",
            self.config.model,
            len(prompt),
            system_prompt is not None,
        )
        response = self._create_completion(prompt=prompt, system_prompt=system_prompt)
        content = self._extract_content(response)
        logger.info("LLM text generation completed: model=%s response_chars=%s", self.config.model, len(content))
        return content

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema_hint: dict[str, Any] | str | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Generate JSON and parse the response.

        Args:
            prompt: User prompt. Do not pass secrets unless required by the use case.
            system_prompt: Optional system instruction.
            schema_hint: Optional JSON schema/example hint appended to the user message.
        """
        json_prompt = self._build_json_prompt(prompt, schema_hint)
        logger.info(
            "Calling LLM JSON generation: provider=deepseek model=%s prompt_chars=%s has_schema_hint=%s",
            self.config.model,
            len(prompt),
            schema_hint is not None,
        )
        response = self._create_completion(
            prompt=json_prompt,
            system_prompt=system_prompt,
            response_format={"type": "json_object"},
        )
        content = self._extract_content(response)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("LLM JSON parsing failed: model=%s response_chars=%s", self.config.model, len(content))
            raise LLMJsonParseError("Model response could not be parsed as JSON") from exc

        logger.info("LLM JSON generation completed: model=%s top_level_type=%s", self.config.model, type(parsed).__name__)
        return parsed

    def stream_generate(self, prompt: str, system_prompt: str | None = None) -> Iterator[str]:
        """Reserved streaming interface for future CrewAI integrations."""
        raise NotImplementedError("stream_generate is reserved for future implementation")

    def _create_completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict[str, str] | None = None,
    ) -> Any:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
        }
        if response_format:
            request["response_format"] = response_format

        try:
            return self.client.chat.completions.create(**request)
        except Exception as exc:
            error_type = type(exc).__name__
            if error_type == "APITimeoutError":
                logger.warning("LLM request timed out: provider=deepseek model=%s", self.config.model)
                raise LLMTimeoutError("DeepSeek request timed out") from exc
            if error_type == "APIConnectionError":
                logger.warning("LLM connection error: provider=deepseek model=%s", self.config.model)
                raise LLMProviderError("DeepSeek connection error") from exc
            if error_type == "APIError" or exc.__class__.__module__.startswith("openai"):
                logger.warning(
                    "LLM provider error: provider=deepseek model=%s error_type=%s",
                    self.config.model,
                    error_type,
                )
                raise LLMProviderError("DeepSeek provider error") from exc
            raise

    @staticmethod
    def _extract_content(response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMEmptyResponseError("Model response did not contain choices")

        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if not content or not content.strip():
            raise LLMEmptyResponseError("Model response content was empty")

        return content.strip()

    @staticmethod
    def _build_json_prompt(prompt: str, schema_hint: dict[str, Any] | str | None) -> str:
        instructions = [
            prompt,
            "Return only valid JSON. Do not include Markdown fences or explanatory text.",
        ]
        if schema_hint is not None:
            if isinstance(schema_hint, str):
                hint = schema_hint
            else:
                hint = json.dumps(schema_hint, ensure_ascii=False)
            instructions.append(f"JSON schema or example hint: {hint}")
        return "\n\n".join(instructions)
