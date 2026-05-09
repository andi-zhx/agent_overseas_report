"""Centralized runtime configuration for local and server deployments.

The module intentionally avoids third-party settings dependencies so the API,
CLI scripts, and tests can all share the same environment-driven configuration.
Secrets are read from environment variables only; never hard-code provider keys
in code or logs.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}

DEFAULT_DATABASE_URL = "sqlite:///.data/overseas_report.sqlite3"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_EMBEDDING_PROVIDER = "local_hashing"
DEFAULT_EMBEDDING_MODEL = "hashing-ngram-v1"
DEFAULT_EMBEDDING_DIMENSIONS = 384
DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
DEFAULT_ALLOWED_UPLOAD_EXTENSIONS = (".pdf", ".docx", ".xlsx", ".pptx", ".md", ".txt")
DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"
DEFAULT_ALLOWED_UPLOAD_MIME_TYPES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/markdown",
    "text/plain",
)
SENSITIVE_ENV_NAMES = ("DEEPSEEK_API_KEY",)


class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class DeepSeekSettings:
    """DeepSeek OpenAI-compatible API settings."""

    api_key: str | None = None
    model: str = DEFAULT_DEEPSEEK_MODEL
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    timeout_seconds: float = 60.0


@dataclass(frozen=True, slots=True)
class EmbeddingSettings:
    """Embedding/vectorization settings for local knowledge-base RAG."""

    provider: str = DEFAULT_EMBEDDING_PROVIDER
    model: str = DEFAULT_EMBEDDING_MODEL
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    vector_dir: Path = Path(".data/knowledge_base_vectors")


@dataclass(frozen=True, slots=True)
class UploadSettings:
    """Upload validation rules for knowledge-base files."""

    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    allowed_extensions: tuple[str, ...] = DEFAULT_ALLOWED_UPLOAD_EXTENSIONS
    allowed_mime_types: tuple[str, ...] = DEFAULT_ALLOWED_UPLOAD_MIME_TYPES


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Application logging settings."""

    level: str = "INFO"
    format: str = DEFAULT_LOG_FORMAT


@dataclass(frozen=True, slots=True)
class AppSettings:
    """All environment-driven settings used by the application."""

    environment: str = "local"
    database_url: str = DEFAULT_DATABASE_URL
    knowledge_base_storage_dir: Path = Path(".data/knowledge_base_uploads")
    deepseek: DeepSeekSettings = field(default_factory=DeepSeekSettings)
    embedding: EmbeddingSettings = field(default_factory=EmbeddingSettings)
    enable_crewai: bool = False
    crewai_verbose: bool = False
    enable_web_research: bool = False
    upload: UploadSettings = field(default_factory=UploadSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = ".env", load_env_file: bool = True) -> "AppSettings":
        """Build settings from environment variables and an optional local .env file."""

        if load_env_file and env_file is not None:
            load_env_file_if_exists(env_file)

        return cls(
            environment=os.getenv("APP_ENV", "local"),
            database_url=os.getenv("OVERSEAS_REPORT_DATABASE_URL", DEFAULT_DATABASE_URL),
            knowledge_base_storage_dir=Path(
                os.getenv("KNOWLEDGE_BASE_STORAGE_DIR", ".data/knowledge_base_uploads")
            ),
            deepseek=DeepSeekSettings(
                api_key=_optional_str(os.getenv("DEEPSEEK_API_KEY")),
                model=os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
                base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL),
                timeout_seconds=_get_float("DEEPSEEK_TIMEOUT_SECONDS", 60.0),
            ),
            embedding=EmbeddingSettings(
                provider=os.getenv("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER),
                model=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
                dimensions=_get_int("EMBEDDING_DIMENSIONS", DEFAULT_EMBEDDING_DIMENSIONS),
                vector_dir=Path(os.getenv("KNOWLEDGE_BASE_VECTOR_DIR", ".data/knowledge_base_vectors")),
            ),
            enable_crewai=_get_bool("ENABLE_CREWAI", False),
            crewai_verbose=_get_bool("CREWAI_VERBOSE", False),
            enable_web_research=_get_bool("ENABLE_WEB_RESEARCH", False),
            upload=UploadSettings(
                max_bytes=_get_int("MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES),
                allowed_extensions=_csv_tuple(
                    os.getenv("ALLOWED_UPLOAD_EXTENSIONS"), DEFAULT_ALLOWED_UPLOAD_EXTENSIONS, normalize_extension=True
                ),
                allowed_mime_types=_csv_tuple(os.getenv("ALLOWED_UPLOAD_MIME_TYPES"), DEFAULT_ALLOWED_UPLOAD_MIME_TYPES),
            ),
            logging=LoggingSettings(level=os.getenv("LOG_LEVEL", "INFO"), format=os.getenv("LOG_FORMAT", DEFAULT_LOG_FORMAT)),
        )

    def validate(self) -> None:
        """Validate settings that could otherwise fail later at runtime."""

        if self.deepseek.timeout_seconds <= 0:
            raise ConfigurationError("DEEPSEEK_TIMEOUT_SECONDS must be greater than 0")
        if self.embedding.dimensions <= 0:
            raise ConfigurationError("EMBEDDING_DIMENSIONS must be greater than 0")
        if self.upload.max_bytes <= 0:
            raise ConfigurationError("MAX_UPLOAD_BYTES must be greater than 0")
        if not self.upload.allowed_extensions:
            raise ConfigurationError("ALLOWED_UPLOAD_EXTENSIONS must not be empty")

    @property
    def has_deepseek_api_key(self) -> bool:
        """Return whether a non-empty DeepSeek key is configured."""

        return bool(self.deepseek.api_key)


class SensitiveDataFilter(logging.Filter):
    """Redact known secret values from log records before handlers emit them."""

    def __init__(self, secrets: Iterable[str | None]) -> None:
        super().__init__()
        self._secrets = tuple(secret for secret in secrets if secret)

    def filter(self, record: logging.LogRecord) -> bool:
        for attr in ("msg",):
            value = getattr(record, attr, None)
            if isinstance(value, str):
                setattr(record, attr, self._redact(value))
        if record.args:
            record.args = tuple(self._redact(arg) if isinstance(arg, str) else arg for arg in record.args)
        return True

    def _redact(self, value: str) -> str:
        redacted = value
        for secret in self._secrets:
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted


def configure_logging(settings: AppSettings | None = None) -> None:
    """Configure root logging with a filter that prevents known secrets leaking."""

    settings = settings or AppSettings.from_env()
    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    logging.basicConfig(level=level, format=settings.logging.format)
    redaction_filter = SensitiveDataFilter([settings.deepseek.api_key, *(os.getenv(name) for name in SENSITIVE_ENV_NAMES)])
    root_logger = logging.getLogger()
    root_logger.addFilter(redaction_filter)
    for handler in root_logger.handlers:
        handler.addFilter(redaction_filter)


def load_env_file_if_exists(path: str | Path) -> None:
    """Load simple KEY=VALUE entries from a .env file without overriding env vars."""

    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        if key and key not in os.environ:
            os.environ[key] = value


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigurationError(f"{name} must be a boolean value")


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc


def _csv_tuple(raw: str | None, default: tuple[str, ...], *, normalize_extension: bool = False) -> tuple[str, ...]:
    if raw is None or raw.strip() == "":
        values = default
    else:
        values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if normalize_extension:
        return tuple(item.lower() if item.startswith(".") else f".{item.lower()}" for item in values)
    return tuple(item.lower() for item in values)


def _optional_str(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
