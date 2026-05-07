from __future__ import annotations

from agent_overseas_report.knowledge_base import get_default_template_repository


REQUIRED_INDUSTRIES = {"建材", "医疗器械", "消费品", "工业设备", "纺织服装", "食品及农产品", "电子产品", "家居用品"}
REQUIRED_COUNTRIES = {"阿联酋", "沙特", "印尼", "越南", "马来西亚", "泰国", "新加坡", "美国", "德国", "墨西哥"}
REQUIRED_RESOURCE_TYPES = {
    "渠道代理商",
    "电商平台",
    "海外仓",
    "物流服务商",
    "认证检测机构",
    "商协会",
    "展会",
    "园区",
    "法律/财税服务机构",
    "技术协作方",
}


def test_default_template_repository_loads_seed_libraries():
    repository = get_default_template_repository()

    assert {item.industry_name for item in repository.industry_templates} == REQUIRED_INDUSTRIES
    assert {item.country_name for item in repository.country_templates} == REQUIRED_COUNTRIES
    assert {item.resource_type for item in repository.resource_templates} == REQUIRED_RESOURCE_TYPES


def test_template_seed_records_have_complete_required_fields():
    repository = get_default_template_repository()

    for template in repository.industry_templates:
        assert template.industry_name
        assert template.typical_products
        assert template.suitable_regions
        assert template.common_entry_modes
        assert template.key_certifications
        assert template.pricing_logic
        assert template.common_channels
        assert template.common_trade_shows
        assert template.major_risks
        assert template.recommended_strategy

    for template in repository.country_templates:
        assert template.country_name
        assert template.region
        assert template.market_opportunity
        assert template.policy_environment
        assert template.tariff_or_access_notes
        assert template.common_channels
        assert template.logistics_notes
        assert template.local_partner_types
        assert template.relevant_trade_shows
        assert template.business_associations
        assert template.entry_difficulty
        assert template.market_potential
        assert template.recommended_industries

    for template in repository.resource_templates:
        assert template.resource_type
        assert template.resource_category
        assert template.resource_subtype
        assert template.description
        assert template.applicable_industries
        assert template.applicable_regions
        assert template.matching_tags
        assert template.selection_criteria
        assert template.maintenance_fields
        assert template.recommended_use


def test_templates_support_matching_by_industry_country_and_resource_type():
    repository = get_default_template_repository()

    assert repository.get_industry("建材").recommended_strategy
    assert repository.get_country("阿联酋").region == "中东"
    assert repository.get_resource_type("海外仓").resource_subtype == "overseas_warehouse"

    middle_east_building_material_countries = repository.match_countries(industry_name="建材", region="中东")
    assert {item.country_name for item in middle_east_building_material_countries} >= {"阿联酋", "沙特"}

    uae_industries = repository.match_industries(country_name="阿联酋")
    assert {item.industry_name for item in uae_industries} >= {"建材", "医疗器械"}

    ecommerce_resources = repository.match_resources(resource_type="电商平台", industry_name="消费品", region="东南亚")
    assert [item.resource_type for item in ecommerce_resources] == ["电商平台"]
