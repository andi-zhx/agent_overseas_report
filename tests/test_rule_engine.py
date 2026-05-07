from __future__ import annotations

from agent_overseas_report.services import OverseasRuleEngine


COMPLETE_PAYLOAD = {
    "enterprise": {"name": "示例医疗科技", "industry": "医疗器械"},
    "products": [
        {
            "name": "家用监测设备",
            "product_type": "诊断设备",
            "hs_code": "901819",
            "overseas_version": True,
            "localized_features": ["英文界面", "欧盟电压适配"],
            "price_band": "中高端",
        }
    ],
    "attachments": ["catalog.pdf", "test-report.pdf"],
    "certifications": ["ISO 13485", "CE MDR"],
    "capacity": {"monthly_units": 12000, "lead_time_days": 30},
    "moq": 100,
    "suppliers": ["核心传感器供应商A", "包装供应商B"],
    "quality_system": "ISO 9001",
    "after_sales": "远程售后 + 备件包",
    "overseas_customers": ["UAE distributor", "Malaysia clinic chain"],
    "overseas_channels": ["注册代理", "区域经销商"],
    "english_materials": ["英文官网", "英文画册", "英文说明书", "英文案例"],
    "team": {"international_members": 4, "languages": ["英语", "阿拉伯语"], "export_years": 3},
    "finance": {"export_budget": 800000, "credit_line": 2000000},
    "target_markets": ["中东", "东南亚"],
    "price_band": "中高端",
}


def test_rule_engine_returns_full_structured_json_without_llm():
    result = OverseasRuleEngine().evaluate(COMPLETE_PAYLOAD)

    assert result["missing_fields"] == []
    assert result["maturity_assessment"]["total_score"] >= 76
    assert result["maturity_assessment"]["maturity_level"] == "全球化布局型"
    assert set(result["maturity_assessment"]["dimension_scores"]) == {
        "product_internationalization",
        "overseas_channel_foundation",
        "english_material_completeness",
        "certification_status",
        "supply_chain_stability",
        "team_internationalization",
        "capital_capacity",
    }
    assert result["maturity_assessment"]["score_explanation"]
    assert result["maturity_assessment"]["improvement_suggestions"] == []

    country_recommendation = result["country_recommendation"]
    assert country_recommendation["primary_markets"]
    assert country_recommendation["secondary_markets"]
    assert country_recommendation["long_term_markets"]
    assert country_recommendation["country_priority_matrix"][0]["recommendation_reasons"]
    assert "market_potential_score" in country_recommendation["country_priority_matrix"][0]
    assert "entry_difficulty_score" in country_recommendation["country_priority_matrix"][0]

    assert result["channel_matches"][0]["channel_type"] in {"经销代理", "海外合资/办事处", "本地KA渠道"}
    assert result["channel_matches"][0]["explanation"]
    assert result["resource_matches"]["展会"]
    assert result["resource_matches"]["认证机构"]
    assert result["resource_matches"]["物流/海外仓"]


def test_rule_engine_reports_missing_fields_instead_of_raising():
    incomplete_payload = {
        "enterprise": {"name": "缺字段企业", "industry": "消费品"},
        "products": [{"name": "小家电"}],
    }

    result = OverseasRuleEngine().evaluate(incomplete_payload)

    assert result["maturity_assessment"]["maturity_level"] == "初级出海型"
    assert "认证情况" in result["missing_fields"]
    assert "英文资料" in result["missing_fields"]
    assert "出海预算/资金能力" in result["maturity_assessment"]["missing_fields"]
    assert result["maturity_assessment"]["improvement_suggestions"]
    assert result["country_recommendation"]["country_priority_matrix"]


def test_country_recommendation_honors_target_market_and_keeps_matrix_scores():
    result = OverseasRuleEngine().evaluate({**COMPLETE_PAYLOAD, "target_markets": ["阿联酋", "沙特"]})

    matrix = result["country_recommendation"]["country_priority_matrix"]
    assert {item["country_name"] for item in matrix} == {"阿联酋", "沙特"}
    assert matrix[0]["priority_rank"] == 1
    assert all(0 <= item["priority_score"] <= 100 for item in matrix)
    assert all(item["explanation"] for item in matrix)
