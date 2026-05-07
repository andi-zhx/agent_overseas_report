"""Pre-generation data completeness checks for overseas-plan generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class GenerationReadinessStatus(str, Enum):
    """Generation quality bands derived from missing required facts."""

    READY = "可生成"
    LOW_QUALITY = "可生成但质量较低"
    NOT_RECOMMENDED = "不建议生成"


@dataclass(frozen=True)
class RequiredFieldRule:
    """Single required field and its possible aliases in the input payload."""

    key: str
    label: str
    aliases: tuple[str, ...]
    critical: bool = False


@dataclass(slots=True)
class MissingFieldCategory:
    """Missing required fields for one business category."""

    category: str
    fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GenerationReadinessReport:
    """Structured response consumed by frontend, backend metadata and DeepSeek prompt."""

    status: GenerationReadinessStatus
    status_code: str
    message: str
    missing_categories: list[MissingFieldCategory]
    missing_count: int
    total_required_count: int
    critical_missing_fields: list[str] = field(default_factory=list)
    should_popup: bool = False
    manual_review_required: bool = False
    prompt_instruction: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


ENTERPRISE_FIELD_RULES: tuple[RequiredFieldRule, ...] = (
    RequiredFieldRule("enterprise_name", "企业名称", ("name", "enterprise_name", "company_name"), critical=True),
    RequiredFieldRule("industry", "所属行业", ("industry", "selected_industry"), critical=True),
    RequiredFieldRule("main_business", "主营业务", ("main_business", "business_scope", "mainProducts", "main_products")),
    RequiredFieldRule("annual_revenue", "年营收", ("annual_revenue", "yearly_revenue", "revenue")),
    RequiredFieldRule("current_markets", "当前市场", ("current_markets", "currentMarkets", "domestic_markets")),
    RequiredFieldRule("export_ratio", "出口占比", ("export_ratio", "exportRatio")),
    RequiredFieldRule("factory_capacity", "工厂产能", ("factory_capacity", "capacity", "production_capacity")),
    RequiredFieldRule("has_overseas_customers", "是否已有海外客户", ("has_overseas_customers", "overseas_customers")),
    RequiredFieldRule("team_internationalization", "团队国际化能力", ("team_internationalization", "team", "international_team")),
    RequiredFieldRule("capital_capacity", "资金能力", ("capital_capacity", "finance", "funding_capacity")),
)

PRODUCT_FIELD_RULES: tuple[RequiredFieldRule, ...] = (
    RequiredFieldRule("product_name", "产品名称", ("name", "product_name"), critical=True),
    RequiredFieldRule("product_category", "产品类别", ("category", "product_category", "type")),
    RequiredFieldRule("hs_code", "HS编码", ("hs_code", "hsCode")),
    RequiredFieldRule("certification_status", "认证情况", ("certifications", "certification_status")),
    RequiredFieldRule("moq", "MOQ", ("moq", "MOQ")),
    RequiredFieldRule("lead_time", "交期", ("lead_time", "lead_time_days", "capacity.lead_time_days", "delivery_time")),
    RequiredFieldRule("price_band", "价格带", ("price_band", "priceBand")),
    RequiredFieldRule("capacity", "产能", ("capacity", "monthly_capacity")),
    RequiredFieldRule("export_suitable", "是否适合出口", ("export_suitable", "suitable_for_export", "overseas_version")),
    RequiredFieldRule("attachments", "产品图片/资料附件", ("attachments", "product_images", "materials")),
)

TARGET_FIELD_RULES: tuple[RequiredFieldRule, ...] = (
    RequiredFieldRule("target_countries", "目标国家", ("target_countries", "target_markets"), critical=True),
    RequiredFieldRule("target_channels", "目标渠道", ("target_channels", "target_channel")),
    RequiredFieldRule("target_customer_types", "目标客户类型", ("target_customer_types", "target_customers")),
    RequiredFieldRule("plan_exhibition", "是否计划参展", ("plan_exhibition", "exhibition_plan")),
    RequiredFieldRule("need_financing", "是否需要融资", ("need_financing", "financing_need")),
    RequiredFieldRule("overseas_warehouse_or_factory", "是否考虑海外仓/海外工厂", ("overseas_warehouse_or_factory", "overseas_warehouse", "overseas_factory")),
)

KEY_FIELD_LABELS = {
    "年营收",
    "出口占比",
    "工厂产能",
    "资金能力",
    "HS编码",
    "认证情况",
    "交期",
    "价格带",
    "是否适合出口",
    "目标国家",
    "目标渠道",
    "目标客户类型",
}


def assess_generation_readiness(enterprise_data: dict[str, Any]) -> GenerationReadinessReport:
    """Assess missing facts before sending an overseas-plan prompt to DeepSeek."""

    enterprise = enterprise_data.get("enterprise") or {}
    products = enterprise_data.get("products") or []
    missing_categories = [
        MissingFieldCategory("企业层面", _missing_for_rule_set(enterprise, ENTERPRISE_FIELD_RULES)),
        MissingFieldCategory("产品层面", _missing_product_fields(products)),
        MissingFieldCategory("出海目标层面", _missing_for_rule_set(enterprise_data, TARGET_FIELD_RULES)),
    ]
    critical_missing = _critical_missing_fields(enterprise, products, enterprise_data)
    missing_count = sum(len(category.fields) for category in missing_categories)
    total_required = len(ENTERPRISE_FIELD_RULES) + len(PRODUCT_FIELD_RULES) + len(TARGET_FIELD_RULES)
    key_missing_count = sum(1 for category in missing_categories for label in category.fields if label in KEY_FIELD_LABELS)

    if critical_missing:
        status = GenerationReadinessStatus.NOT_RECOMMENDED
        message = "缺失企业名称、所属行业、产品名称或目标国家等基础字段，不建议直接生成。"
        should_popup = True
    elif key_missing_count >= 4 or missing_count >= 10:
        status = GenerationReadinessStatus.LOW_QUALITY
        message = "信息可用于生成，但缺失较多关键字段，方案质量和可执行性会降低。"
        should_popup = False
    else:
        status = GenerationReadinessStatus.READY
        message = "信息基本完整，可生成企业出海方案。"
        should_popup = False

    manual_review_required = status != GenerationReadinessStatus.READY or missing_count > 0
    prompt_instruction = _build_prompt_instruction(missing_categories, status, manual_review_required)
    return GenerationReadinessReport(
        status=status,
        status_code=status.name.lower(),
        message=message,
        missing_categories=[category for category in missing_categories if category.fields],
        missing_count=missing_count,
        total_required_count=total_required,
        critical_missing_fields=critical_missing,
        should_popup=should_popup,
        manual_review_required=manual_review_required,
        prompt_instruction=prompt_instruction,
    )


def _missing_for_rule_set(payload: dict[str, Any], rules: tuple[RequiredFieldRule, ...]) -> list[str]:
    return [rule.label for rule in rules if not any(_has_value(_deep_get(payload, alias)) for alias in rule.aliases)]


def _missing_product_fields(products: Any) -> list[str]:
    if not isinstance(products, list) or not products:
        return [rule.label for rule in PRODUCT_FIELD_RULES]
    missing = []
    for rule in PRODUCT_FIELD_RULES:
        if not all(any(_has_value(_deep_get(product, alias)) for alias in rule.aliases) for product in products if isinstance(product, dict)):
            missing.append(rule.label)
    return missing


def _critical_missing_fields(enterprise: dict[str, Any], products: Any, enterprise_data: dict[str, Any]) -> list[str]:
    critical = []
    if "企业名称" in _missing_for_rule_set(enterprise, ENTERPRISE_FIELD_RULES):
        critical.append("企业名称")
    if "所属行业" in _missing_for_rule_set(enterprise, ENTERPRISE_FIELD_RULES):
        critical.append("所属行业")
    if "产品名称" in _missing_product_fields(products):
        critical.append("产品名称")
    if "目标国家" in _missing_for_rule_set(enterprise_data, TARGET_FIELD_RULES):
        critical.append("目标国家")
    return critical


def _build_prompt_instruction(categories: list[MissingFieldCategory], status: GenerationReadinessStatus, manual_review_required: bool) -> str:
    missing_text = "；".join(f"{category.category}: {', '.join(category.fields)}" for category in categories if category.fields)
    if not missing_text:
        missing_text = "无明显缺失字段"
    review_text = "必须在方案中标记“需人工补充/复核”" if manual_review_required else "正常生成"
    return (
        f"生成前数据完整性状态：{status.value}。缺失字段：{missing_text}。"
        f"{review_text}；对缺失字段不得编造具体事实、数值、机构名称、认证状态、价格、产能或客户信息，"
        "只能基于已提供数据进行保守推断，并在 data_quality_notes/global_manual_review_items 中说明。"
    )


def _deep_get(payload: dict[str, Any], alias: str) -> Any:
    current: Any = payload
    for part in alias.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True
