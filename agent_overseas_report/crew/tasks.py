"""Task definitions for the three-step CrewAI overseas-plan workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agent_overseas_report.prompts import INVESTMENT_GRADE_REPORT_MODULES, LEGACY_SEVEN_SECTION_KEYS, STANDARD_MODULE_FIELDS


@dataclass(frozen=True, slots=True)
class CrewTaskSpec:
    """Dependency-light task specification used by the runner and CrewAI adapter."""

    name: str
    agent_name: str
    description: str
    expected_output: str


def create_task_specs() -> list[CrewTaskSpec]:
    """Return the minimum three tasks aligned to the three agents."""

    return [
        CrewTaskSpec(
            name="research_summary",
            agent_name="research",
            description="整理本地 RAG、WebResearch 和 context_bundle，输出研究摘要、证据边界和待复核缺口。",
            expected_output="中文研究摘要；只包含事实、来源线索、缺口和人工复核提示。",
        ),
        CrewTaskSpec(
            name="strategy_generation",
            agent_name="strategy",
            description="基于研究摘要、规则引擎输出和企业事实，生成国家优先级、进入模式、资源动作和路线图策略。",
            expected_output="中文策略方案；不输出最终报告 JSON。",
        ),
        CrewTaskSpec(
            name="report_json",
            agent_name="report",
            description="将策略和原始生成提示整合为兼容现有 schema 的结构化报告 JSON。",
            expected_output="只输出合法 JSON 对象，包含 investment_analysis_report 和 legacy sections。",
        ),
    ]


def build_research_prompt(*, local_context: list[dict[str, Any]], web_research_context: list[dict[str, Any]], context_bundle: dict[str, Any]) -> str:
    return (
        "你是 ResearchAgent，只负责整理本地 RAG 和 WebResearch 结果。\n"
        "请输出中文研究摘要，必须区分：已提供事实、有来源资料、信息缺口、需人工复核事项。\n"
        "不要生成策略，不要生成最终报告 JSON。\n\n"
        f"输入资料：\n{_to_json({'local_rag': local_context, 'web_research': web_research_context, 'context_bundle': context_bundle})}"
    )


def build_strategy_prompt(*, enterprise_data: dict[str, Any], rule_engine_output: dict[str, Any], research_summary: str) -> str:
    return (
        "你是 StrategyAgent，只负责基于研究摘要和规则引擎输出生成出海策略。\n"
        "请输出国家优先级、进入模式、渠道/资源动作、融资扩产动作、12-24个月路线图和关键风险。\n"
        "不要生成最终报告 JSON；动态政策/关税/市场规模若来源不足必须写需人工复核。\n\n"
        f"输入资料：\n{_to_json({'enterprise_data': enterprise_data, 'rule_engine_output': rule_engine_output, 'research_summary': research_summary})}"
    )


def build_report_prompt(*, original_user_prompt: str, research_summary: str, strategy_output: str, json_structure_example: dict[str, Any]) -> str:
    return (
        "你是 ReportAgent，只负责将策略整合为结构化报告 JSON。\n"
        "请严格复用原始报告 prompt 的输出合同，不要删除原有 prompt 约束。\n"
        "最终只输出一个合法 JSON 对象，不要 Markdown，不要解释。\n"
        f"必须包含 investment_analysis_report 模块：{', '.join(INVESTMENT_GRADE_REPORT_MODULES)}。\n"
        f"每个升级模块必须包含字段：{', '.join(STANDARD_MODULE_FIELDS)}。\n"
        f"必须保留兼容 sections：{', '.join(LEGACY_SEVEN_SECTION_KEYS)}。\n\n"
        f"研究摘要：\n{research_summary}\n\n"
        f"策略输出：\n{strategy_output}\n\n"
        f"JSON结构示例：\n{_to_json(json_structure_example)}\n\n"
        f"原始报告生成 prompt：\n{original_user_prompt}"
    )


def _to_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
