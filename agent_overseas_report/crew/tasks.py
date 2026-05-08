"""Task definitions for the enterprise CrewAI overseas-report workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agent_overseas_report.crew.config import default_agent_configs
from agent_overseas_report.prompts import INVESTMENT_GRADE_REPORT_MODULES, LEGACY_SEVEN_SECTION_KEYS, STANDARD_MODULE_FIELDS


@dataclass(frozen=True, slots=True)
class CrewTaskSpec:
    """Dependency-light task specification used by the runner and CrewAI adapter."""

    name: str
    agent_name: str
    description: str
    expected_output: str
    save_key: str


TASK_SEQUENCE: tuple[tuple[str, str, str], ...] = (
    ("company_diagnosis", "company_diagnosis", "企业与产品诊断"),
    ("market_research", "market_research", "市场与国家研究"),
    ("channel_strategy", "channel_strategy", "渠道策略设计"),
    ("resource_matching", "resource_matching", "资源匹配"),
    ("financial_planning", "financial_planning", "投融资与扩产分析"),
    ("risk_compliance", "risk_compliance", "合规与风险检查"),
    ("report_writing", "report_writer", "报告撰写"),
    ("quality_review", "quality_review", "质量复核"),
)


def create_task_specs() -> list[CrewTaskSpec]:
    """Return the sequential tasks aligned to the complete enterprise crew."""

    configs = default_agent_configs()
    return [
        CrewTaskSpec(
            name=name,
            agent_name=agent_name,
            description=(
                f"{label}。只使用统一传入的 ContextBundle 与上游步骤输出；不得自行访问数据库；"
                "不得编造数据；所有事实和判断必须保留 citations。"
            ),
            expected_output=configs[agent_name].output_spec,
            save_key=name,
        )
        for name, agent_name, label in TASK_SEQUENCE
    ]


def build_agent_prompt(
    *,
    agent_name: str,
    task_name: str,
    task_label: str,
    context_bundle: dict[str, Any],
    upstream_outputs: dict[str, Any],
    extra_inputs: dict[str, Any] | None = None,
) -> str:
    """Build a constrained prompt for one non-report task."""

    config = default_agent_configs()[agent_name]
    payload = {
        "task_name": task_name,
        "task_label": task_label,
        "context_bundle": context_bundle,
        "upstream_outputs": upstream_outputs,
        "extra_inputs": extra_inputs or {},
    }
    return (
        f"你是 {config.role}，当前步骤：{task_label}。\n"
        f"目标：{config.goal}\n"
        f"背景：{config.backstory}\n\n"
        f"{config.instruction_block()}\n\n"
        "输出必须可单独保存和审计。请优先输出结构化 JSON；如无法确认事实，请写入 data_gaps/manual_review_items，"
        "不要补造数值、政策、市场规模、渠道名单或预算。\n\n"
        f"输入资料：\n{_to_json(payload)}"
    )


def build_report_prompt(
    *,
    original_user_prompt: str,
    step_outputs: dict[str, Any],
    context_bundle: dict[str, Any],
    json_structure_example: dict[str, Any],
) -> str:
    config = default_agent_configs()["report_writer"]
    return (
        f"你是 {config.role}，只负责将上游步骤产出整合为结构化报告 JSON。\n"
        f"目标：{config.goal}\n"
        f"背景：{config.backstory}\n\n"
        f"{config.instruction_block()}\n\n"
        "请严格复用原始报告 prompt 的输出合同，不要删除原有 prompt 约束。\n"
        "最终只输出一个合法 JSON 对象，不要 Markdown，不要解释。\n"
        "不得自行访问数据库；只能使用 ContextBundle 与上游步骤输出。\n"
        "所有事实、数字、政策、风险、预算和资源建议必须保留 citations；缺来源则标记需人工复核。\n"
        f"必须包含 investment_analysis_report 模块：{', '.join(INVESTMENT_GRADE_REPORT_MODULES)}。\n"
        f"每个升级模块必须包含字段：{', '.join(STANDARD_MODULE_FIELDS)}。\n"
        f"必须保留兼容 sections：{', '.join(LEGACY_SEVEN_SECTION_KEYS)}。\n\n"
        f"ContextBundle：\n{_to_json(context_bundle)}\n\n"
        f"上游步骤输出：\n{_to_json(step_outputs)}\n\n"
        f"JSON结构示例：\n{_to_json(json_structure_example)}\n\n"
        f"原始报告生成 prompt：\n{original_user_prompt}"
    )


def build_quality_review_prompt(*, report_json_text: str, step_outputs: dict[str, Any], context_bundle: dict[str, Any]) -> str:
    config = default_agent_configs()["quality_review"]
    return (
        f"你是 {config.role}，负责最终质量复核。\n"
        f"目标：{config.goal}\n"
        f"背景：{config.backstory}\n\n"
        f"{config.instruction_block()}\n\n"
        "请只输出合法 JSON，不要 Markdown。JSON 必须包含：status、issues、required_revisions、"
        "citations_check、specificity_check、budget_assumption_check。\n"
        "质量门槛：\n"
        "1. 缺少来源/citations 的事实、数据、政策、风险或资源建议 => status 必须为 revision_required；\n"
        "2. 结论空泛、没有企业/产品/国家/渠道/时间动作细节 => status 必须为 revision_required；\n"
        "3. 预算、融资、扩产、现金流结论没有清晰假设 => status 必须为 revision_required；\n"
        "4. 只有全部通过时才能返回 status=approved。\n\n"
        f"ContextBundle：\n{_to_json(context_bundle)}\n\n"
        f"上游步骤输出：\n{_to_json(step_outputs)}\n\n"
        f"待复核报告 JSON 文本：\n{report_json_text}"
    )


# Backward-compatible helper names kept for callers/tests that import them directly.
def build_research_prompt(*, local_context: list[dict[str, Any]], web_research_context: list[dict[str, Any]], context_bundle: dict[str, Any]) -> str:
    merged_context = {**context_bundle, "local_chunks": local_context, "web_research_sources": web_research_context}
    return build_agent_prompt(
        agent_name="market_research",
        task_name="market_research",
        task_label="市场与国家研究",
        context_bundle=merged_context,
        upstream_outputs={},
    )


def build_strategy_prompt(*, enterprise_data: dict[str, Any], rule_engine_output: dict[str, Any], research_summary: str) -> str:
    return build_agent_prompt(
        agent_name="channel_strategy",
        task_name="channel_strategy",
        task_label="渠道策略设计",
        context_bundle={"enterprise_data": enterprise_data, "rule_engine_outputs": rule_engine_output},
        upstream_outputs={"market_research": research_summary},
    )


def _to_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
