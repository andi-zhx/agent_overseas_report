"""Minimal CrewAI orchestration package for overseas-plan generation."""

from .agents import MinimalAgent, create_agents
from .config import CrewAISettings, CrewAgentConfig, is_crewai_enabled, load_packaged_config
from .crew import MinimalCrew, create_overseas_plan_crew
from .crew_runner import CrewOverseasPlanRunner, CrewRunResult
from .tasks import CrewTaskSpec, create_task_specs

__all__ = [
    "CrewAISettings",
    "CrewAgentConfig",
    "CrewOverseasPlanRunner",
    "CrewRunResult",
    "CrewTaskSpec",
    "MinimalAgent",
    "MinimalCrew",
    "create_agents",
    "create_overseas_plan_crew",
    "create_task_specs",
    "is_crewai_enabled",
    "load_packaged_config",
]
