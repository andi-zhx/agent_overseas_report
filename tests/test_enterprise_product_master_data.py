from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from agent_overseas_report.schemas import EnterpriseCreate, ImportValidationRequest, ProductCreate
from agent_overseas_report.routers.enterprises import validate_enterprise_import, validate_product_import


def valid_enterprise_payload() -> dict[str, object]:
    return {
        "id": "ent-api",
        "name": "测试智能装备有限公司",
        "unified_social_credit_code": "91310000MA1K000000",
        "industry": "智能装备",
        "enterprise_nature": "民营企业",
        "established_at": "2019-05-20",
        "region": "江苏省苏州市",
        "main_business": "工业检测设备研发、生产和销售",
        "core_products": ["视觉检测设备"],
        "annual_revenue_range": "1亿-5亿元",
        "export_experience": "已通过贸易商出口东南亚市场",
        "current_export_countries": ["越南", "泰国"],
        "capacity_status": {"monthly_units": 300, "utilization_rate": "75%"},
        "certifications": ["ISO 9001", "CE"],
        "financing_needs": {"amount": 20000000, "purpose": "新增海外版产线和渠道库存"},
        "overseas_goals": ["建立东南亚经销渠道", "获取本地大客户"],
        "investment_profile": {"gross_margin": "42%", "revenue_growth": "30%"},
        "market_entry_preferences": {"priority_regions": ["东盟"], "entry_modes": ["经销", "本地集成商"]},
        "channel_requirements": {"partner_types": ["工业自动化集成商"]},
        "expansion_plan": {"new_capacity": "月产500台", "capex": 30000000},
    }


def valid_product_payload() -> dict[str, object]:
    return {
        "id": "prod-api",
        "enterprise_id": "ent-api",
        "name": "AI 视觉检测设备",
        "product_category": "工业检测设备",
        "hs_code": "903149",
        "application_scenarios": ["电子制造质检", "汽车零部件质检"],
        "core_selling_points": ["缺陷识别准确率高", "部署周期短"],
        "technical_parameters": {"accuracy": "99%", "throughput": "120件/分钟"},
        "price_range": "USD 20000-50000",
        "moq": "1套",
        "capacity": {"monthly_units": 300, "lead_time_days": 45},
        "certifications": ["CE"],
        "target_customers": ["电子制造工厂", "汽车零部件工厂"],
        "competitors": ["海外机器视觉品牌A"],
        "export_restrictions": "需核验目标国工业设备安全标准",
        "compliance_requirements": ["CE", "当地电气安全标准"],
        "investment_highlights": ["软件订阅续费", "高毛利售后服务"],
        "market_entry_notes": {"recommended_mode": "本地集成商合作"},
        "channel_fit": {"preferred_channels": ["自动化集成商", "行业展会"]},
        "financing_expansion_assumptions": {"inventory_months": 3},
    }


def test_enterprise_and_product_schema_accept_structured_report_inputs() -> None:
    enterprise = EnterpriseCreate(**valid_enterprise_payload())
    product = ProductCreate(**valid_product_payload())

    assert enterprise.investment_profile["gross_margin"] == "42%"
    assert enterprise.market_entry_preferences["priority_regions"] == ["东盟"]
    assert product.enterprise_id == enterprise.id
    assert product.channel_fit["preferred_channels"] == ["自动化集成商", "行业展会"]


def test_import_validation_reports_enterprise_and_product_field_errors() -> None:
    enterprise_records = [valid_enterprise_payload(), {"name": "字段缺失企业", "unified_social_credit_code": "bad"}]
    product_records = [valid_product_payload(), {"enterprise_id": "ent-api", "name": "字段缺失产品", "hs_code": "ABC"}]

    enterprise_result = validate_enterprise_import(ImportValidationRequest(records=enterprise_records))
    product_result = validate_product_import(ImportValidationRequest(records=product_records))

    assert enterprise_result.valid_count == 1
    assert enterprise_result.invalid_count == 1
    assert any(issue.row == 2 and issue.field == "industry" for issue in enterprise_result.issues)
    assert any(issue.row == 2 and issue.field == "unified_social_credit_code" for issue in enterprise_result.issues)
    assert product_result.valid_count == 1
    assert product_result.invalid_count == 1
    assert any(issue.row == 2 and issue.field == "product_category" for issue in product_result.issues)
    assert any(issue.row == 2 and issue.field == "hs_code" for issue in product_result.issues)


@pytest.mark.parametrize("schema,payload", [(EnterpriseCreate, valid_enterprise_payload()), (ProductCreate, valid_product_payload())])
def test_schema_rejects_blank_required_names(schema: type, payload: dict[str, object]) -> None:
    payload["name"] = ""

    with pytest.raises(Exception):
        schema(**payload)
