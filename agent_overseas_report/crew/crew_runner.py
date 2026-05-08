"""Runner that bridges the existing LLM port into the minimal CrewAI workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agent_overseas_report.crew.config import CrewAISettings
from agent_overseas_report.crew.crew import create_overseas_plan_crew
from agent_overseas_report.crew.tasks import build_report_prompt, build_research_prompt, build_strategy_prompt


class TextLLMClient(Protocol):
    """LLM interface required by the crew runner."""

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text for one task prompt."""


@dataclass(slots=True)
class CrewRunResult:
    """Output and trace metadata from the three-agent crew workflow."""

    report_json_text: str
    research_summary: str
    strategy_output: str
    metadata: dict[str, Any]


@dataclass(slots=True)
class CrewOverseasPlanRunner:
    """Execute the minimum viable Research → Strategy → Report crew."""

    llm_client: TextLLMClient
    settings: CrewAISettings | None = None

    def run(
        self,
        *,
        prompt_bundle: Any,
        enterprise_data: dict[str, Any],
        rule_engine_output: dict[str, Any],
        local_context: list[dict[str, Any]],
        web_research_context: list[dict[str, Any]],
        context_bundle: dict[str, Any],
    ) -> CrewRunResult:
        """Run the three single-responsibility agents and return final JSON text."""

        settings = self.settings or CrewAISettings.from_env()
        crew = create_overseas_plan_crew(settings=settings)

        research_summary = self.llm_client.generate_text(
            build_research_prompt(
                local_context=local_context,
                web_research_context=web_research_context,
                context_bundle=context_bundle,
            ),
            system_prompt="你是 ResearchAgent。只做研究摘要，不做策略或报告 JSON。",
        )
        strategy_output = self.llm_client.generate_text(
            build_strategy_prompt(
                enterprise_data=enterprise_data,
                rule_engine_output=rule_engine_output,
                research_summary=research_summary,
            ),
            system_prompt="你是 StrategyAgent。只做出海策略，不做最终报告 JSON。",
        )
        report_json_text = self.llm_client.generate_text(
            build_report_prompt(
                original_user_prompt=prompt_bundle.user_prompt,
                research_summary=research_summary,
                strategy_output=strategy_output,
                json_structure_example=prompt_bundle.json_structure_example,
            ),
            system_prompt=prompt_bundle.system_prompt,
        )
        return CrewRunResult(
            report_json_text=report_json_text,
            research_summary=research_summary,
            strategy_output=strategy_output,
            metadata={
                "enabled": settings.enabled,
                "process": settings.process,
                "agent_count": 3,
                "agents": ["ResearchAgent", "StrategyAgent", "ReportAgent"],
                "crew_adapter": crew.__class__.__name__,
            },
        )
