"""企业出海方案生成模块的数据结构定义。

当前项目尚未引入 ORM 或数据库迁移机制，因此本文件采用标准库
``dataclasses`` + ``Enum`` 定义可序列化的领域模型，便于后续无缝映射到
数据库表、Pydantic Schema 或本地 JSON 持久化结构。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class GenerationStatus(str, Enum):
    """出海方案生成任务状态，支持异步生成流程扩展。"""

    DRAFT = "draft"
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MaturityLevel(str, Enum):
    """企业出海成熟度分级。"""

    BEGINNER = "初级出海型"
    GROWTH = "增长型"
    GLOBAL_LAYOUT = "全球化布局型"


class ResourceCategory(str, Enum):
    """海外资源库一级类型。"""

    CHANNEL = "channel"
    TECHNOLOGY = "technology"
    SUPPLY_CHAIN = "supply_chain"
    GOVERNMENT_INSTITUTION = "government_institution"
    EXHIBITION = "exhibition"


class ResourceSubType(str, Enum):
    """海外资源库二级类型，覆盖渠道、技术、供应链、政府机构和展会资源。"""

    DISTRIBUTOR = "distributor"
    AGENT = "agent"
    KA_CHANNEL = "ka_channel"
    ECOMMERCE_PLATFORM = "ecommerce_platform"
    LOCAL_TECH_PARTNER = "local_tech_partner"
    TESTING_CERTIFICATION = "testing_certification"
    RD_COLLABORATOR = "rd_collaborator"
    OVERSEAS_WAREHOUSE = "overseas_warehouse"
    LOGISTICS = "logistics"
    MANUFACTURING_PARTNER = "manufacturing_partner"
    BUSINESS_ASSOCIATION = "business_association"
    INDUSTRIAL_PARK = "industrial_park"
    TRADE_PROMOTION_AGENCY = "trade_promotion_agency"
    INVESTMENT_PROMOTION_AGENCY = "investment_promotion_agency"
    INTERNATIONAL_EXHIBITION = "international_exhibition"
    INDUSTRY_EXHIBITION = "industry_exhibition"
    PROMOTION_EVENT = "promotion_event"
    PROCUREMENT_MATCHMAKING = "procurement_matchmaking"


MATURITY_SCORE_WEIGHTS: dict[str, int] = {
    # 产品是否具备多语言、标准适配、海外场景适配能力，满分 20 分。
    "product_internationalization": 20,
    # 是否已有海外经销、代理、平台、KA 等渠道基础，满分 20 分。
    "overseas_channel_foundation": 20,
    # 官网、画册、说明书、案例、视频等英文资料完整度，满分 10 分。
    "english_material_completeness": 10,
    # 目标市场所需认证、检测、准入资质准备情况，满分 15 分。
    "certification_status": 15,
    # 交付、物流、产能、关键物料与售后供应链稳定性，满分 15 分。
    "supply_chain_stability": 15,
    # 团队语言、外贸、法务、财税、本地化运营能力，满分 10 分。
    "team_internationalization": 10,
    # 出海营销、认证、备货、渠道建设与本地化投入能力，满分 10 分。
    "capital_capacity": 10,
}


COUNTRY_SELECTION_DIMENSIONS: tuple[str, ...] = (
    # 目标国家/地区的需求规模、增长潜力与客户匹配度。
    "market_demand",
    # 贸易准入、产业政策、关税、投资和合规环境。
    "policy_environment",
    # 本地竞品强度、价格带、差异化空间和替代品风险。
    "competitive_environment",
    # 经销、KA、电商、服务商等商业渠道成熟度。
    "channel_maturity",
    # 物流、仓储、制造协同、售后和备件体系适配性。
    "supply_chain_fit",
)


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间，统一新增模型的时间字段口径。"""

    return datetime.now(timezone.utc)


@dataclass(slots=True)
class GeneratedFileRef:
    """生成文件引用，兼容 URL 存储和本地/对象存储路径。"""

    url: str | None = None
    file_path: str | None = None


@dataclass(slots=True)
class MaturityDimensionScore:
    """企业出海成熟度单项评分。"""

    dimension: str
    score: float
    max_score: int
    comment: str | None = None
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MaturityAssessment:
    """企业出海成熟度评估结果，总分 100 分并输出成熟度分级。"""

    total_score: float
    maturity_level: MaturityLevel
    dimension_scores: list[MaturityDimensionScore]
    summary: str | None = None
    improvement_suggestions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CountryDimensionScore:
    """国家选择五维模型的单项评分。"""

    dimension: str
    score: float
    max_score: int = 100
    rationale: str | None = None


@dataclass(slots=True)
class CountryPriorityMatrixItem:
    """推荐目标国家及优先级矩阵数据。"""

    country_code: str
    country_name: str
    priority_rank: int
    total_score: float
    dimension_scores: list[CountryDimensionScore]
    recommended_entry_mode: str | None = None
    key_opportunities: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OverseasResource:
    """海外资源库对象，用于资源对接清单和后续资源库沉淀。"""

    id: str
    name: str
    category: ResourceCategory
    subtype: ResourceSubType
    country_code: str | None = None
    country_name: str | None = None
    region: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website_url: str | None = None
    capability_tags: list[str] = field(default_factory=list)
    matched_product_ids: list[str] = field(default_factory=list)
    match_score: float | None = None
    notes: str | None = None
    source: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class OverseasGenerationResult:
    """企业出海方案生成结果的结构化正文。"""

    enterprise_diagnosis: dict[str, Any] = field(default_factory=dict)
    product_competitiveness_analysis: dict[str, Any] = field(default_factory=dict)
    maturity_assessment: MaturityAssessment | None = None
    recommended_target_countries: list[str] = field(default_factory=list)
    country_priority_matrix: list[CountryPriorityMatrixItem] = field(default_factory=list)
    recommended_entry_modes: list[dict[str, Any]] = field(default_factory=list)
    channel_path_design: list[dict[str, Any]] = field(default_factory=list)
    overseas_resource_matches: list[OverseasResource] = field(default_factory=list)
    exhibition_and_marketing_plan: list[dict[str, Any]] = field(default_factory=list)
    financing_and_capacity_plan: dict[str, Any] = field(default_factory=dict)
    implementation_roadmap_12_24_months: list[dict[str, Any]] = field(default_factory=list)
    risk_warnings: list[dict[str, Any]] = field(default_factory=list)
    next_action_suggestions: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GenerationProject:
    """出海方案生成项目，不修改现有企业和产品表，仅通过 ID 建立弱关联。"""

    id: str
    enterprise_id: str
    product_ids: list[str]
    selected_industry: str
    target_countries: list[str]
    generation_status: GenerationStatus = GenerationStatus.DRAFT
    generated_by: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    version: int = 1
    final_score: float | None = None
    maturity_level: MaturityLevel | None = None
    output_word: GeneratedFileRef | None = None
    output_ppt: GeneratedFileRef | None = None
    output_excel: GeneratedFileRef | None = None
    result: OverseasGenerationResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为适合 JSON 持久化或 API 响应的字典结构。"""

        return _serialize(asdict(self))


def infer_maturity_level(total_score: float) -> MaturityLevel:
    """根据 100 分制总分推断企业出海成熟度分级。

    分级口径：0-40 为初级出海型，41-75 为增长型，76-100 为全球化布局型。
    """

    if total_score >= 76:
        return MaturityLevel.GLOBAL_LAYOUT
    if total_score >= 41:
        return MaturityLevel.GROWTH
    return MaturityLevel.BEGINNER


def _serialize(value: Any) -> Any:
    """递归序列化 Enum 和 datetime，确保模型可直接写入本地 JSON。"""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value
