"""Agent definitions for the enterprise CrewAI overseas-report crew."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any

from agent_overseas_report.crew.config import CrewAISettings, CrewAgentConfig


@dataclass(frozen=True, slots=True)
class MinimalAgent:
    """Dependency-light representation of one CrewAI agent role."""

    name: str
    role: str
    goal: str
    backstory: str
    input_spec: str
    output_spec: str
    constraints: tuple[str, ...]
    allow_delegation: bool = False


def create_agents(settings: CrewAISettings | None = None, llm: Any | None = None) -> dict[str, Any]:
    """Create the enterprise overseas-report agents.

    When the optional ``crewai`` package is importable this returns real
    ``crewai.Agent`` instances. Otherwise it returns ``MinimalAgent`` objects so
    tests and offline deployments can still exercise the orchestration contract.
    """

    settings = settings or CrewAISettings.from_env()
    configs = settings.agent_configs
    return {
        name: _create_agent(name=name, config=config, llm=llm, verbose=settings.verbose)
        for name, config in configs.items()
    }


def _create_agent(*, name: str, config: CrewAgentConfig, llm: Any | None, verbose: bool) -> Any:
    if find_spec("crewai") is None:
        return MinimalAgent(
            name=name,
            role=config.role,
            goal=config.goal,
            backstory=config.backstory,
            input_spec=config.input_spec,
            output_spec=config.output_spec,
            constraints=config.constraints,
            allow_delegation=config.allow_delegation,
        )

    from crewai import Agent

    kwargs: dict[str, Any] = {
        "role": config.role,
        "goal": config.goal,
        "backstory": f"{config.backstory}\n\n{config.instruction_block()}",
        "allow_delegation": config.allow_delegation,
        "verbose": verbose,
    }
    if llm is not None:
        kwargs["llm"] = llm
    return Agent(**kwargs)
