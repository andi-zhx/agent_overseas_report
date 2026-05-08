"""Prompt templates for DeepSeek overseas-expansion plan generation.

This module keeps the system prompt, user-prompt assembly, and required JSON
shape in one place so business services can call DeepSeek without embedding
large prompt fragments inline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

OVERSEAS_PLAN_SYSTEM_PROMPT = """你是咨询公司合伙人级别的企业出海战略顾问，擅长将企业数据、规则引擎结果和资源库信息转化为可直接进入 Word/PPT 的结构化出海方案。

请严格遵守以下要求：
1. 只输出一个合法 JSON 对象，不要输出 Markdown、解释性前后缀或代码块。
2. 输出必须覆盖 01-07 七大模块，模块命名、顺序和字段语义必须与用户提示中的 JSON 结构示例一致。
3. 语言风格为咨询公司交付稿：专业、结构清晰、结论先行、可用于前端预览和后续导出。
4. 避免空泛表述。每条建议必须结合企业产品、所属行业、目标国家/区域、渠道阶段或资源类型中的至少一个具体要素。
5. 不得编造具体不存在的企业、机构、代理商、联系人、电话、邮箱、网址或未提供的合作案例。
6. 如果资源库没有提供具体资源名称，只能写“建议对接类型”，并说明该类型与企业产品/行业/国家的匹配原因。
7. 涉及关税、政策、准入规则、认证有效性、市场规模、增长率、招投标规则、补贴政策等动态信息时，必须在对应条目中标注“需人工复核”。
8. 若输入数据不足，不要臆造；应在 relevant_data_gaps、data_quality_notes 或 risk_notes 中说明缺口，并给出补齐动作。
9. 如果 enterprise_data.generation_readiness 或 extra_context.generation_readiness 标记缺失字段，必须把缺失项作为事实缺口处理，不得补写虚构值；若 manual_review_required=true，方案中必须出现“需人工补充/复核”。
10. JSON 字段值应使用中文；金额、时间、评分等可保留输入中的原始单位，并在必要时说明假设。
"""

OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE: dict[str, Any] = {
    "report_title": "企业出海方案",
    "version": "v1",
    "language": "zh-CN",
    "sections": {
        "01_enterprise_diagnosis": {
            "title": "01 企业现状诊断",
            "enterprise_basic_profile": {
                "summary": "企业基础情况摘要",
                "key_facts": ["企业名称/行业/产品/产能/认证等关键事实"],
                "relevant_data_gaps": ["缺失信息及补齐动作"]
            },
            "product_competitiveness_analysis": [
                {
                    "product_or_line": "产品名称或产品线",
                    "competitive_strengths": ["结合产品、认证、价格带、交付能力的优势"],
                    "competitive_constraints": ["结合目标市场的约束"],
                    "improvement_actions": ["可执行补齐建议"]
                }
            ],
            "overseas_maturity_assessment": {
                "total_score": 0,
                "maturity_level": "初级出海型/增长型/全球化布局型",
                "dimension_scores": [
                    {
                        "dimension": "维度名称",
                        "score": 0,
                        "max_score": 0,
                        "evidence": ["来自企业数据或规则引擎的证据"],
                        "consulting_interpretation": "咨询解读"
                    }
                ],
                "summary": "成熟度结论"
            },
            "current_shortcomings_and_fixes": [
                {
                    "shortcoming": "当前短板",
                    "impact": "对目标国家/渠道/资源对接的影响",
                    "fix_suggestion": "补齐建议",
                    "priority": "高/中/低"
                }
            ]
        },
        "02_overseas_market_selection": {
            "title": "02 海外市场选择",
            "recommended_country_tiers": {
                "tier_1_primary": ["国家/区域"],
                "tier_2_secondary": ["国家/区域"],
                "tier_3_long_term": ["国家/区域"]
            },
            "country_selection_five_dimension_model": [
                {
                    "country": "国家",
                    "market_demand": {"score": 0, "rationale": "需求判断；动态信息标注需人工复核"},
                    "policy_environment": {"score": 0, "rationale": "政策/准入判断；动态信息标注需人工复核"},
                    "competitive_environment": {"score": 0, "rationale": "竞争格局判断"},
                    "channel_maturity": {"score": 0, "rationale": "渠道成熟度判断"},
                    "supply_chain_fit": {"score": 0, "rationale": "物流、仓储、售后、供应链适配"}
                }
            ],
            "country_priority_matrix": [
                {
                    "country": "国家",
                    "priority_rank": 1,
                    "priority_score": 0,
                    "recommended_entry_mode": "推荐模式",
                    "key_opportunities": ["机会"],
                    "key_risks": ["风险；动态信息标注需人工复核"]
                }
            ],
            "entry_reasons_by_country": [
                {
                    "country": "国家",
                    "entry_reasons": ["每个国家的进入理由，需结合产品、行业、渠道或资源"],
                    "manual_review_notes": ["需人工复核的政策/关税/市场规模等"]
                }
            ]
        },
        "03_entry_mode_design": {
            "title": "03 出海模式设计",
            "recommended_entry_path": "总体进入路径",
            "stage_1_channels": [{"stage": "第一阶段", "channel": "渠道", "actions": ["动作"], "rationale": "适配原因"}],
            "stage_2_channels": [{"stage": "第二阶段", "channel": "渠道", "actions": ["动作"], "rationale": "适配原因"}],
            "stage_3_layout": [{"stage": "第三阶段", "layout": "布局", "actions": ["动作"], "rationale": "适配原因"}],
            "mode_fit_reasons": [{"mode": "模式", "fit_reason": "结合企业成熟度、产品、国家和资源类型说明"}]
        },
        "04_overseas_resource_matching_plan": {
            "title": "04 海外资源对接方案",
            "channel_resources": [{"resource_name": "资源名称或建议对接类型", "country_or_region": "国家/区域", "matching_reason": "匹配原因", "next_step": "下一步"}],
            "technology_resources": [{"resource_name": "资源名称或建议对接类型", "country_or_region": "国家/区域", "matching_reason": "匹配原因", "next_step": "下一步"}],
            "supply_chain_resources": [{"resource_name": "资源名称或建议对接类型", "country_or_region": "国家/区域", "matching_reason": "匹配原因", "next_step": "下一步"}],
            "government_and_association_resources": [{"resource_name": "资源名称或建议对接类型", "country_or_region": "国家/区域", "matching_reason": "匹配原因", "next_step": "下一步"}],
            "resource_connection_priority": [{"priority_rank": 1, "resource_type": "资源类型", "target_country": "国家/区域", "reason": "优先级原因", "owner": "责任方"}]
        },
        "05_exhibition_and_marketing_plan": {
            "title": "05 展会与市场推广计划",
            "exhibition_strategy": [{"target_country_or_region": "国家/区域", "resource_name_or_type": "展会名称或建议对接类型", "objective": "目标", "manual_review_notes": ["档期/费用等动态信息需人工复核"]}],
            "promotion_event_strategy": [{"target_country_or_region": "国家/区域", "theme": "推介会主题", "target_audience": "目标受众", "actions": ["动作"]}],
            "procurement_matchmaking_strategy": [{"target_country_or_region": "国家/区域", "buyer_type": "采购方类型", "matching_logic": "匹配逻辑", "actions": ["动作"]}],
            "overseas_customer_acquisition_funnel": [{"funnel_stage": "触达/线索/验证/转化/复购", "key_actions": ["动作"], "metrics": ["指标"]}],
            "pre_during_post_exhibition_actions": {
                "before": ["展前动作"],
                "during": ["展中动作"],
                "after": ["展后动作"]
            }
        },
        "06_financing_and_capacity_expansion_plan": {
            "title": "06 投融资与扩产规划",
            "capacity_planning": [{"phase": "阶段", "capacity_action": "产能动作", "trigger_condition": "触发条件", "risk_notes": ["风险"]}],
            "financing_planning": [{"phase": "阶段", "funding_need": "资金需求", "financing_option": "融资方式", "usage": "资金用途"}],
            "capital_synergy_path": [{"partner_type": "资本/产业伙伴类型", "synergy_logic": "协同逻辑", "next_step": "下一步"}],
            "industrial_fund_participation": [{"participation_method": "参与方式", "suitable_timing": "适合时点", "manual_review_notes": ["基金政策/条件需人工复核"]}]
        },
        "07_12_24_month_implementation_roadmap": {
            "title": "07 12-24个月实施路线图",
            "roadmap": [
                {"period": "1-3个月", "objectives": ["目标"], "actions": ["动作"], "responsible_parties": ["责任方"], "deliverables": ["交付物"]},
                {"period": "3-6个月", "objectives": ["目标"], "actions": ["动作"], "responsible_parties": ["责任方"], "deliverables": ["交付物"]},
                {"period": "6-9个月", "objectives": ["目标"], "actions": ["动作"], "responsible_parties": ["责任方"], "deliverables": ["交付物"]},
                {"period": "9-12个月", "objectives": ["目标"], "actions": ["动作"], "responsible_parties": ["责任方"], "deliverables": ["交付物"]},
                {"period": "12-24个月", "objectives": ["目标"], "actions": ["动作"], "responsible_parties": ["责任方"], "deliverables": ["交付物"]}
            ]
        }
    },
    "global_manual_review_items": ["所有关税、政策、市场规模、展会档期和基金条件等动态信息需人工复核"],
    "data_quality_notes": ["基于输入数据形成的缺口说明"],
    "data_quality_review": {"status": "可生成/可生成但质量较低/不建议生成", "manual_review_required": False, "missing_categories": []}
}


@dataclass(frozen=True)
class OverseasPlanPromptBundle:
    """System/user prompt pair plus the required JSON structure example."""

    system_prompt: str
    user_prompt: str
    json_structure_example: dict[str, Any]


def build_overseas_plan_prompts(
    *,
    enterprise_data: dict[str, Any],
    rule_engine_output: dict[str, Any],
    resource_library: dict[str, Any] | list[Any] | None = None,
    extra_context: dict[str, Any] | None = None,
    retrieved_context: list[dict[str, Any]] | None = None,
) -> OverseasPlanPromptBundle:
    """Build the complete DeepSeek prompt bundle for overseas-plan generation.

    Args:
        enterprise_data: Raw enterprise/product facts submitted by the user or upstream system.
        rule_engine_output: Deterministic recommendations produced by ``OverseasRuleEngine.evaluate``.
        resource_library: Optional concrete resource matches. If omitted or empty, the model must use
            "建议对接类型" instead of invented names.
        extra_context: Optional project metadata such as report version, selected language, or operator notes.
    """

    return OverseasPlanPromptBundle(
        system_prompt=OVERSEAS_PLAN_SYSTEM_PROMPT,
        user_prompt=build_overseas_plan_user_prompt(
            enterprise_data=enterprise_data,
            rule_engine_output=rule_engine_output,
            resource_library=resource_library,
            extra_context=extra_context,
            retrieved_context=retrieved_context,
        ),
        json_structure_example=OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE,
    )


def build_overseas_plan_user_prompt(
    *,
    enterprise_data: dict[str, Any],
    rule_engine_output: dict[str, Any],
    resource_library: dict[str, Any] | list[Any] | None = None,
    extra_context: dict[str, Any] | None = None,
    retrieved_context: list[dict[str, Any]] | None = None,
) -> str:
    """Assemble the user prompt from enterprise facts, rule output, resources, and JSON shape."""

    resource_payload: dict[str, Any] | list[Any] | str
    if resource_library:
        resource_payload = resource_library
    else:
        resource_payload = "未提供具体资源名称；涉及资源时只能输出“建议对接类型”，不得编造机构、代理商或联系方式。"

    prompt_payload = {
        "enterprise_data": enterprise_data,
        "rule_engine_output": rule_engine_output,
        "resource_library": resource_payload,
        "extra_context": extra_context or {},
        "retrieved_context": retrieved_context or [],
        "generation_readiness": (extra_context or {}).get("generation_readiness") or enterprise_data.get("generation_readiness") or {},
        "required_json_structure_example": OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE,
    }

    return (
        "请基于以下输入，为企业生成完整的出海方案 JSON。\n"
        "组装逻辑：以 enterprise_data 作为企业事实底座；以 rule_engine_output 作为国家、成熟度、渠道、资源匹配的优先参考；"
        "resource_library 仅用于引用真实存在的资源名称；retrieved_context 是本地知识库与 WebResearchService 检索到的补充上下文且必须保留来源；required_json_structure_example 是必须遵循的输出结构。\n"
        "重要约束：不得编造未提供的具体资源名称或联系方式；没有具体资源名称时写“建议对接类型”；"
        "缺失字段已通过 generation_readiness 传入，必须原样视为数据缺口，不能编造；若 manual_review_required=true，必须在方案中标记“需人工补充/复核”；"
        "关税、政策、市场规模、展会档期、基金条件等动态信息必须标注“需人工复核”；"
        "RAG 只作为上下文增强，WebResearchService 也只作为有来源的外部资料补充，不得直接替代 enterprise_data、rule_engine_output 或既有报告生成逻辑；引用 retrieved_context 时需结合其来源元数据；没有来源的数据必须标注“需人工复核”。"
        "每条建议都要结合企业产品、行业、国家或资源类型，避免空泛。\n\n"
        f"输入数据如下：\n{_to_pretty_json(prompt_payload)}"
    )


def _to_pretty_json(payload: Any) -> str:
    """Serialize prompt payloads with stable Chinese-friendly formatting."""

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
