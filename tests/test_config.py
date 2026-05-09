from __future__ import annotations

import logging

import pytest

from agent_overseas_report.config import AppSettings, ConfigurationError, SensitiveDataFilter


def test_settings_loads_env_without_real_secret(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-placeholder-key")
    monkeypatch.setenv("ENABLE_CREWAI", "true")
    monkeypatch.setenv("ENABLE_WEB_RESEARCH", "yes")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "128")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")
    monkeypatch.setenv("ALLOWED_UPLOAD_EXTENSIONS", ".txt,md")

    settings = AppSettings.from_env(load_env_file=False)

    assert settings.has_deepseek_api_key is True
    assert settings.deepseek.api_key == "test-placeholder-key"
    assert settings.enable_crewai is True
    assert settings.enable_web_research is True
    assert settings.embedding.dimensions == 128
    assert settings.upload.max_bytes == 1024
    assert settings.upload.allowed_extensions == (".txt", ".md")


def test_settings_rejects_invalid_upload_size(monkeypatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "0")
    settings = AppSettings.from_env(load_env_file=False)

    with pytest.raises(ConfigurationError, match="MAX_UPLOAD_BYTES"):
        settings.validate()


def test_sensitive_data_filter_redacts_known_secret() -> None:
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "provider failed: sk-secret", (), None)
    filter_ = SensitiveDataFilter(["sk-secret"])

    assert filter_.filter(record) is True
    assert "sk-secret" not in record.msg
    assert "[REDACTED]" in record.msg
