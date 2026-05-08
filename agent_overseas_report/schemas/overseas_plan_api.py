"""Pydantic request/response schemas for the overseas-plan FastAPI layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateOverseasPlanRequest(BaseModel):
    """Request body for creating and synchronously generating an overseas plan."""

    enterprise_id: str = Field(..., min_length=1, description="Enterprise identifier supplied by upstream systems.")
    product_ids: list[str] = Field(..., min_length=1, description="Selected product IDs under the enterprise.")
    selected_industry: str = Field(..., min_length=1, description="Industry selected for template/rule matching.")
    target_countries: list[str] = Field(..., min_length=1, description="Target countries or regions for the plan.")
    generated_by: str = Field(..., min_length=1, description="User ID that starts generation.")
    project_id: str | None = Field(default=None, description="Optional caller-provided project ID.")
    extra_context: dict[str, Any] = Field(default_factory=dict, description="Additional generation context.")
    continue_on_validation_warning: bool = Field(default=False, description="Continue even when readiness warnings are raised.")
    username: str | None = Field(default=None, description="Display name for audit logs.")


class RegenerateOverseasPlanRequest(BaseModel):
    """Request body for regenerating a plan from an existing project."""

    generated_by: str = Field(..., min_length=1, description="User ID that starts regeneration.")
    extra_context: dict[str, Any] = Field(default_factory=dict, description="Regeneration reason and additional context.")
    username: str | None = Field(default=None, description="Display name for audit logs.")


class FinalizeOverseasPlanRequest(BaseModel):
    """Request body for marking a content version as final."""

    version_number: int = Field(..., ge=1, description="Content version number to mark as final.")
    finalized_by: str = Field(..., min_length=1, description="User ID that marks the final version.")
    username: str | None = Field(default=None, description="Display name for audit logs.")


class ErrorResponse(BaseModel):
    """Standard error response payload."""

    detail: str


class HealthResponse(BaseModel):
    """Health-check response payload."""

    status: str
    service: str


class OverseasPlanGenerationResponse(BaseModel):
    """Response body for generate/regenerate endpoints."""

    project: dict[str, Any]
    preview: dict[str, Any] | None = None
    audit_log: dict[str, Any]


class OverseasPlanDetailResponse(BaseModel):
    """Response body for plan detail lookup."""

    project: dict[str, Any]


class OverseasPlanVersionListResponse(BaseModel):
    """Response body for listing content versions."""

    project_id: str
    current_version_number: int | None = None
    final_version_number: int | None = None
    versions: list[dict[str, Any]]


class FinalizeOverseasPlanResponse(BaseModel):
    """Response body after marking a version as final."""

    version: dict[str, Any]


class EnterpriseBase(BaseModel):
    """Structured enterprise fields for overseas-report input."""

    model_config = {"extra": "allow"}

    name: str = Field(..., min_length=1, description="企业名称。")
    unified_social_credit_code: str = Field(..., min_length=18, max_length=18, pattern=r"^[0-9A-Z]{18}$", description="统一社会信用代码。")
    industry: str = Field(..., min_length=1, description="所属行业。")
    enterprise_nature: str = Field(..., min_length=1, description="企业性质，如民营、国有、外资、合资。")
    established_at: str = Field(..., min_length=4, description="成立时间，建议使用 YYYY-MM-DD。")
    region: str = Field(..., min_length=1, description="所在地区。")
    main_business: str = Field(..., min_length=1, description="主营业务。")
    core_products: list[str] = Field(..., min_length=1, description="核心产品。")
    annual_revenue_range: str = Field(..., min_length=1, description="年营收区间。")
    export_experience: str = Field(..., min_length=1, description="出口经验。")
    current_export_countries: list[str] = Field(default_factory=list, description="当前出口国家。")
    capacity_status: dict[str, Any] = Field(default_factory=dict, description="产能情况。")
    certifications: list[str] = Field(default_factory=list, description="认证情况。")
    financing_needs: dict[str, Any] = Field(default_factory=dict, description="融资需求。")
    overseas_goals: list[str] = Field(..., min_length=1, description="出海诉求。")
    investment_profile: dict[str, Any] = Field(default_factory=dict, description="投资分析所需画像，如盈利能力、增长率、估值偏好。")
    market_entry_preferences: dict[str, Any] = Field(default_factory=dict, description="市场进入偏好，如目标区域、进入模式、风险偏好。")
    channel_requirements: dict[str, Any] = Field(default_factory=dict, description="渠道匹配要求，如经销商、KA、跨境电商或服务商能力。")
    expansion_plan: dict[str, Any] = Field(default_factory=dict, description="融资扩产分析所需计划，如新增产线、CAPEX、产能爬坡。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据。")


class EnterpriseCreate(EnterpriseBase):
    """Create-enterprise payload."""

    id: str | None = Field(default=None, description="企业 ID；为空时由后端生成。")


class EnterpriseUpdate(BaseModel):
    """Partial enterprise update payload."""

    model_config = {"extra": "allow"}

    name: str | None = Field(default=None, min_length=1)
    unified_social_credit_code: str | None = Field(default=None, min_length=18, max_length=18, pattern=r"^[0-9A-Z]{18}$")
    industry: str | None = Field(default=None, min_length=1)
    enterprise_nature: str | None = Field(default=None, min_length=1)
    established_at: str | None = Field(default=None, min_length=4)
    region: str | None = Field(default=None, min_length=1)
    main_business: str | None = Field(default=None, min_length=1)
    core_products: list[str] | None = None
    annual_revenue_range: str | None = Field(default=None, min_length=1)
    export_experience: str | None = Field(default=None, min_length=1)
    current_export_countries: list[str] | None = None
    capacity_status: dict[str, Any] | None = None
    certifications: list[str] | None = None
    financing_needs: dict[str, Any] | None = None
    overseas_goals: list[str] | None = None
    investment_profile: dict[str, Any] | None = None
    market_entry_preferences: dict[str, Any] | None = None
    channel_requirements: dict[str, Any] | None = None
    expansion_plan: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class EnterpriseResponse(EnterpriseBase):
    """Enterprise API response."""

    id: str
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None


class ProductBase(BaseModel):
    """Structured product fields for overseas-report input."""

    model_config = {"extra": "allow"}

    enterprise_id: str = Field(..., min_length=1, description="所属企业 ID。")
    name: str = Field(..., min_length=1, description="产品名称。")
    product_category: str = Field(..., min_length=1, description="产品类别。")
    hs_code: str = Field(..., min_length=4, max_length=10, pattern=r"^[0-9]{4,10}$", description="HS 编码。")
    application_scenarios: list[str] = Field(..., min_length=1, description="应用场景。")
    core_selling_points: list[str] = Field(..., min_length=1, description="核心卖点。")
    technical_parameters: dict[str, Any] = Field(default_factory=dict, description="技术参数。")
    price_range: str = Field(..., min_length=1, description="价格区间。")
    moq: str = Field(..., min_length=1, description="MOQ。")
    capacity: dict[str, Any] = Field(default_factory=dict, description="产能。")
    certifications: list[str] = Field(default_factory=list, description="认证。")
    target_customers: list[str] = Field(default_factory=list, description="目标客户。")
    competitors: list[str] = Field(default_factory=list, description="竞品。")
    export_restrictions: str | None = Field(default=None, description="出口限制。")
    compliance_requirements: list[str] = Field(default_factory=list, description="合规要求。")
    investment_highlights: list[str] = Field(default_factory=list, description="投资分析亮点。")
    market_entry_notes: dict[str, Any] = Field(default_factory=dict, description="市场进入分析补充。")
    channel_fit: dict[str, Any] = Field(default_factory=dict, description="渠道匹配分析补充。")
    financing_expansion_assumptions: dict[str, Any] = Field(default_factory=dict, description="融资扩产分析假设。")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductCreate(ProductBase):
    """Create-product payload."""

    id: str | None = Field(default=None, description="产品 ID；为空时由后端生成。")


class ProductUpdate(BaseModel):
    """Partial product update payload."""

    model_config = {"extra": "allow"}

    enterprise_id: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)
    product_category: str | None = Field(default=None, min_length=1)
    hs_code: str | None = Field(default=None, min_length=4, max_length=10, pattern=r"^[0-9]{4,10}$")
    application_scenarios: list[str] | None = None
    core_selling_points: list[str] | None = None
    technical_parameters: dict[str, Any] | None = None
    price_range: str | None = Field(default=None, min_length=1)
    moq: str | None = Field(default=None, min_length=1)
    capacity: dict[str, Any] | None = None
    certifications: list[str] | None = None
    target_customers: list[str] | None = None
    competitors: list[str] | None = None
    export_restrictions: str | None = None
    compliance_requirements: list[str] | None = None
    investment_highlights: list[str] | None = None
    market_entry_notes: dict[str, Any] | None = None
    channel_fit: dict[str, Any] | None = None
    financing_expansion_assumptions: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class ProductResponse(ProductBase):
    """Product API response."""

    id: str
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None


class ImportValidationRequest(BaseModel):
    """Generic import-validation request for enterprises or products."""

    records: list[dict[str, Any]] = Field(..., min_length=1, description="待导入记录列表。")


class ImportValidationIssue(BaseModel):
    """One field-level import-validation issue."""

    row: int
    field: str
    message: str


class ImportValidationResponse(BaseModel):
    """Import-validation response without writing records."""

    valid_count: int
    invalid_count: int
    issues: list[ImportValidationIssue]
