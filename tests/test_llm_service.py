from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_overseas_report.services.llm_service import (
    DeepSeekLLMConfig,
    DeepSeekLLMService,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMJsonParseError,
)


class FakeCompletions:
    def __init__(self, content: str | None) -> None:
        self.content = content
        self.last_request = None

    def create(self, **request):
        self.last_request = request
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class FakeClient:
    def __init__(self, content: str | None) -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def make_service(content: str | None) -> DeepSeekLLMService:
    config = DeepSeekLLMConfig(api_key="test-key", model="deepseek-chat")
    return DeepSeekLLMService(config=config, client=FakeClient(content))


def test_missing_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(LLMConfigurationError):
        DeepSeekLLMConfig.from_env()


def test_generate_text_returns_content():
    service = make_service("hello")

    assert service.generate_text("Say hello") == "hello"


def test_generate_text_rejects_empty_content():
    service = make_service("   ")

    with pytest.raises(LLMEmptyResponseError):
        service.generate_text("Say hello")


def test_generate_json_parses_valid_json():
    service = make_service('{"status":"ok"}')

    assert service.generate_json("Return status") == {"status": "ok"}
    assert service.client.completions.last_request["response_format"] == {"type": "json_object"}


def test_generate_json_raises_for_invalid_json():
    service = make_service("not json")

    with pytest.raises(LLMJsonParseError):
        service.generate_json("Return status")
