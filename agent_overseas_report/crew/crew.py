"""Crew construction helpers for the enterprise multi-agent workflow."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any

from agent_overseas_report.crew.agents import create_agents
from agent_overseas_report.crew.config import CrewAISettings
from agent_overseas_report.crew.tasks import CrewTaskSpec, create_task_specs


@dataclass(frozen=True, slots=True)
class MinimalCrew:
    """Dependency-light crew descriptor for offline-safe orchestration."""

    agents: dict[str, Any]
    tasks: list[CrewTaskSpec]
    process: str = "sequential"


def create_overseas_plan_crew(settings: CrewAISettings | None = None, llm: Any | None = None) -> Any:
    """Create the enterprise CrewAI crew descriptor.

    If CrewAI is installed and all agents are real CrewAI agents, this returns a
    ``crewai.Crew`` with sequential process. Otherwise it returns ``MinimalCrew``.
    """

    settings = settings or CrewAISettings.from_env()
    agents = create_agents(settings=settings, llm=llm)
    task_specs = create_task_specs()

    if find_spec("crewai") is None:
        return MinimalCrew(agents=agents, tasks=task_specs, process=settings.process)

    from crewai import Crew, Process, Task

    if any(agent.__class__.__name__ == "MinimalAgent" for agent in agents.values()):
        return MinimalCrew(agents=agents, tasks=task_specs, process=settings.process)

    tasks = [
        Task(
            description=spec.description,
            expected_output=spec.expected_output,
            agent=agents[spec.agent_name],
        )
        for spec in task_specs
    ]
    process = Process.sequential if settings.process == "sequential" else settings.process
    return Crew(agents=list(agents.values()), tasks=tasks, process=process, verbose=settings.verbose)
