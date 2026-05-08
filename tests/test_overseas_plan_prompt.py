from __future__ import annotations

import json

from agent_overseas_report.prompts import (
    INVESTMENT_GRADE_REPORT_MODULES,
    LEGACY_SEVEN_SECTION_KEYS,
    OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE,
    OVERSEAS_PLAN_SYSTEM_PROMPT,
    STANDARD_MODULE_FIELDS,
    build_overseas_plan_prompts,
    build_overseas_plan_user_prompt,
)


def test_system_prompt_contains_investment_grade_constraints():
    assert "只输出一个合法 JSON 对象" in OVERSEAS_PLAN_SYSTEM_PROMPT
    assert "一级市场投资分析师" in OVERSEAS_PLAN_SYSTEM_PROMPT
    assert "不得编造具体不存在的企业、机构、代理商" in OVERSEAS_PLAN_SYSTEM_PROMPT
    assert "不允许无来源输出具体市场规模、增长率、关税、政策、展会时间" in OVERSEAS_PLAN_SYSTEM_PROMPT
    assert "需人工复核" in OVERSEAS_PLAN_SYSTEM_PROMPT


def test_json_structure_example_contains_required_eighteen_modules_and_legacy_sections():
    report = OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE["investment_analysis_report"]
    sections = OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE["sections"]

    assert list(report) == list(INVESTMENT_GRADE_REPORT_MODULES)
    assert list(sections) == list(LEGACY_SEVEN_SECTION_KEYS)
    for module in INVESTMENT_GRADE_REPORT_MODULES:
        for field_name in STANDARD_MODULE_FIELDS:
            assert field_name in report[module]
    assert "enterprise_basic_profile" in sections["01_enterprise_diagnosis"]
    assert "country_selection_five_dimension_model" in sections["02_overseas_market_selection"]
    assert "stage_1_channels" in sections["03_entry_mode_design"]
    assert "resource_connection_priority" in sections["04_overseas_resource_matching_plan"]
    assert "pre_during_post_exhibition_actions" in sections["05_exhibition_and_marketing_plan"]
    assert "industrial_fund_participation" in sections["06_financing_and_capacity_expansion_plan"]
    roadmap = sections["07_12_24_month_implementation_roadmap"]["roadmap"]
    assert [item["period"] for item in roadmap] == ["1-3个月", "3-6个月", "6-9个月", "9-12个月", "12-24个月"]


def test_user_prompt_embeds_inputs_and_fallback_resource_instruction():
    user_prompt = build_overseas_plan_user_prompt(
        enterprise_data={"enterprise": {"name": "示例企业", "industry": "医疗器械"}},
        rule_engine_output={"maturity_assessment": {"total_score": 88}},
    )

    assert "示例企业" in user_prompt
    assert "医疗器械" in user_prompt
    assert "未提供具体资源名称" in user_prompt
    assert "建议对接类型" in user_prompt
    assert "investment_analysis_report" in user_prompt
    assert "legacy_compatibility_sections" in user_prompt
    assert "不允许无来源输出具体市场规模" in user_prompt

    payload = user_prompt.split("输入数据如下：\n", maxsplit=1)[1]
    parsed = json.loads(payload)
    assert parsed["enterprise_data"]["enterprise"]["name"] == "示例企业"
    assert parsed["rule_engine_output"]["maturity_assessment"]["total_score"] == 88
    assert parsed["retrieved_context"] == []
    assert parsed["required_report_modules"] == list(INVESTMENT_GRADE_REPORT_MODULES)


def test_build_prompt_bundle_supports_system_and_user_prompts():
    bundle = build_overseas_plan_prompts(
        enterprise_data={"enterprise": {"name": "示例企业"}},
        rule_engine_output={"country_recommendation": {"recommended_country_names": ["阿联酋"]}},
        resource_library={"渠道资源": [{"name": "真实资源A"}]},
        extra_context={"version": "demo"},
        retrieved_context=[{"chunk_id": "chunk-1", "file_name": "source.txt", "text": "德国渠道资料"}],
    )

    assert bundle.system_prompt == OVERSEAS_PLAN_SYSTEM_PROMPT
    assert "真实资源A" in bundle.user_prompt
    assert "阿联酋" in bundle.user_prompt
    assert "德国渠道资料" in bundle.user_prompt
    assert "source.txt" in bundle.user_prompt
    assert bundle.json_structure_example == OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE
