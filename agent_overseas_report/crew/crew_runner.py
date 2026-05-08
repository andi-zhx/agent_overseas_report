"""Runner that bridges the existing LLM port into the enterprise CrewAI workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from agent_overseas_report.crew.config import CrewAISettings
from agent_overseas_report.crew.crew import create_overseas_plan_crew
from agent_overseas_report.crew.tasks import TASK_SEQUENCE, build_agent_prompt, build_quality_review_prompt, build_report_prompt


class TextLLMClient(Protocol):
    """LLM interface required by the crew runner."""

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text for one task prompt."""


@dataclass(slots=True)
class CrewStepOutput:
    """One saveable step output from the enterprise crew workflow."""

    task_name: str
    agent_name: str
    agent_role: str
    output_text: str
    save_key: str


@dataclass(slots=True)
class CrewRunResult:
    """Output and trace metadata from the enterprise crew workflow."""

    report_json_text: str
    research_summary: str
    strategy_output: str
    metadata: dict[str, Any]
    step_outputs: dict[str, str] = field(default_factory=dict)
    quality_review: str = ""
    quality_status: str = "unknown"


@dataclass(slots=True)
class CrewOverseasPlanRunner:
    """Execute the enterprise multi-agent overseas-report crew."""

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
        """Run all agents sequentially and return final JSON text plus saveable traces."""

        settings = self.settings or CrewAISettings.from_env()
        crew = create_overseas_plan_crew(settings=settings)
        agent_configs = settings.agent_configs
        step_outputs: dict[str, str] = {}
        traces: list[dict[str, str]] = []

        enriched_context_bundle = {
            **context_bundle,
            "enterprise_data": context_bundle.get("enterprise_data", enterprise_data),
            "rule_engine_outputs": context_bundle.get("rule_engine_outputs", rule_engine_output),
            "local_chunks": context_bundle.get("local_chunks", local_context),
            "web_research_sources": context_bundle.get("web_research_sources", web_research_context),
        }
        extra_inputs = {
            "enterprise_data": enterprise_data,
            "rule_engine_output": rule_engine_output,
            "local_context_count": len(local_context),
            "web_research_context_count": len(web_research_context),
        }

        for task_name, agent_name, task_label in TASK_SEQUENCE:
            if agent_name == "report_writer":
                output_text = self.llm_client.generate_text(
                    build_report_prompt(
                        original_user_prompt=prompt_bundle.user_prompt,
                        step_outputs=step_outputs,
                        context_bundle=enriched_context_bundle,
                        json_structure_example=prompt_bundle.json_structure_example,
                    ),
                    system_prompt=prompt_bundle.system_prompt,
                )
            elif agent_name == "quality_review":
                output_text = self.llm_client.generate_text(
                    build_quality_review_prompt(
                        report_json_text=step_outputs.get("report_writing", ""),
                        step_outputs=step_outputs,
                        context_bundle=enriched_context_bundle,
                    ),
                    system_prompt="你是 QualityReviewAgent。只做质量复核；缺来源、结论空泛或预算无假设时必须返回 revision_required。",
                )
            else:
                output_text = self.llm_client.generate_text(
                    build_agent_prompt(
                        agent_name=agent_name,
                        task_name=task_name,
                        task_label=task_label,
                        context_bundle=enriched_context_bundle,
                        upstream_outputs=step_outputs,
                        extra_inputs=extra_inputs,
                    ),
                    system_prompt=f"你是 {agent_configs[agent_name].role}。只执行当前步骤，不访问数据库，不编造数据，必须使用 citations。",
                )

            step_outputs[task_name] = output_text
            traces.append(
                {
                    "task_name": task_name,
                    "agent_name": agent_name,
                    "agent_role": agent_configs[agent_name].role,
                    "save_key": task_name,
                    "output_text": output_text,
                }
            )

        quality_review = step_outputs.get("quality_review", "")
        quality_status = _extract_quality_status(quality_review)
        report_json_text = step_outputs.get("report_writing", "")
        agent_roles = [agent_configs[agent_name].role for _, agent_name, _ in TASK_SEQUENCE]

        return CrewRunResult(
            report_json_text=report_json_text,
            research_summary=step_outputs.get("market_research", ""),
            strategy_output=step_outputs.get("channel_strategy", ""),
            step_outputs=step_outputs,
            quality_review=quality_review,
            quality_status=quality_status,
            metadata={
                "enabled": settings.enabled,
                "process": settings.process,
                "agent_count": len(agent_roles),
                "agents": agent_roles,
                "tasks": [task_name for task_name, _, _ in TASK_SEQUENCE],
                "crew_adapter": crew.__class__.__name__,
                "saveable_step_outputs": traces,
                "quality_status": quality_status,
            },
        )


def _extract_quality_status(review_text: str) -> str:
    """Extract the QualityReviewAgent status from JSON or plain text."""

    try:
        parsed = json.loads(review_text)
    except json.JSONDecodeError:
        lowered = review_text.lower()
        if "revision_required" in lowered:
            return "revision_required"
        if "approved" in lowered:
            return "approved"
        return "unknown"
    if isinstance(parsed, dict):
        status = parsed.get("status")
        if status in {"approved", "revision_required"}:
            return status
    return "unknown"
