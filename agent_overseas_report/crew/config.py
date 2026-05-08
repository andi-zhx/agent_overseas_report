"""Configuration helpers for the minimal CrewAI orchestration path."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True, slots=True)
class CrewAgentConfig:
    """Static configuration for one CrewAI agent role."""

    role: str
    goal: str
    backstory: str
    allow_delegation: bool = False


@dataclass(frozen=True, slots=True)
class CrewAISettings:
    """Runtime settings for the minimal CrewAI report workflow."""

    enabled: bool = False
    process: str = "sequential"
    verbose: bool = False
    agent_configs: dict[str, CrewAgentConfig] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "CrewAISettings":
        """Build settings from environment variables.

        CrewAI is intentionally opt-in so the legacy ``OverseasPlanGenerationService``
        path remains the default production behavior.
        """

        enabled = os.getenv("ENABLE_CREWAI", "").strip().lower() in _TRUE_VALUES
        verbose = os.getenv("CREWAI_VERBOSE", "").strip().lower() in _TRUE_VALUES
        return cls(enabled=enabled, verbose=verbose, agent_configs=default_agent_configs())


def is_crewai_enabled() -> bool:
    """Return whether the CrewAI orchestration path should be used."""

    return CrewAISettings.from_env().enabled


def default_agent_configs() -> dict[str, CrewAgentConfig]:
    """Return the three-agent configuration for the minimum viable crew."""

    return {
        "research": CrewAgentConfig(
            role="ResearchAgent",
            goal="整理本地 RAG 和 WebResearch 结果，形成有来源边界的研究摘要。",
            backstory="专注证据梳理和缺口识别，不直接生成策略或最终报告。",
        ),
        "strategy": CrewAgentConfig(
            role="StrategyAgent",
            goal="基于研究摘要和规则引擎输出生成企业出海策略。",
            backstory="专注战略判断、国家优先级、进入路径和资源动作，不负责最终 JSON 排版。",
        ),
        "report": CrewAgentConfig(
            role="ReportAgent",
            goal="将策略整合为兼容现有报告 JSON schema 的结构化报告。",
            backstory="专注 JSON 合同、字段完整性和旧版 sections 兼容，不新增额外 Agent 职责。",
        ),
    }


def config_file_path() -> Path:
    """Return the packaged CrewAI config file path for documentation/tooling."""

    return Path(__file__).with_name("crew_config.json")


def load_packaged_config() -> dict[str, Any]:
    """Load the lightweight packaged CrewAI config without extra YAML dependencies."""

    import json

    return json.loads(config_file_path().read_text(encoding="utf-8"))
