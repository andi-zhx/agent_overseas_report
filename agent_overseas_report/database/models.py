"""SQLAlchemy ORM models for overseas-plan persistence."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for database mappings."""


class TimestampStatusMetadataMixin:
    """Shared auditability columns required on all business tables."""

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", SQLiteJSON, nullable=False, default=dict)


class EnterpriseORM(TimestampStatusMetadataMixin, Base):
    """Structured enterprise master data used by overseas-report generation."""

    __tablename__ = "enterprises"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unified_social_credit_code: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(128), index=True)
    enterprise_nature: Mapped[str | None] = mapped_column(String(64))
    established_at: Mapped[date | None] = mapped_column(Date)
    region: Mapped[str | None] = mapped_column(String(128), index=True)
    main_business: Mapped[str | None] = mapped_column(Text)
    core_products: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    annual_revenue_range: Mapped[str | None] = mapped_column(String(128))
    export_experience: Mapped[str | None] = mapped_column(Text)
    current_export_countries: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    capacity_status: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    certifications: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    financing_needs: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    overseas_goals: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    investment_profile: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    market_entry_preferences: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    channel_requirements: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    expansion_plan: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)

    products: Mapped[list[ProductORM]] = relationship(back_populates="enterprise", cascade="all, delete-orphan")


class ProductORM(TimestampStatusMetadataMixin, Base):
    """Structured product master data linked to one enterprise."""

    __tablename__ = "products"

    enterprise_id: Mapped[str] = mapped_column(ForeignKey("enterprises.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    product_category: Mapped[str | None] = mapped_column(String(128), index=True)
    hs_code: Mapped[str | None] = mapped_column(String(32), index=True)
    application_scenarios: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    core_selling_points: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    technical_parameters: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    price_range: Mapped[str | None] = mapped_column(String(128))
    moq: Mapped[str | None] = mapped_column(String(128))
    capacity: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    certifications: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    target_customers: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    competitors: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    export_restrictions: Mapped[str | None] = mapped_column(Text)
    compliance_requirements: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    investment_highlights: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    market_entry_notes: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    channel_fit: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    financing_expansion_assumptions: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)

    enterprise: Mapped[EnterpriseORM] = relationship(back_populates="products")


class OverseasGenerationProjectORM(TimestampStatusMetadataMixin, Base):
    """Persisted overseas-plan generation project."""

    __tablename__ = "overseas_generation_projects"

    enterprise_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_ids: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    selected_industry: Mapped[str] = mapped_column(String(128), nullable=False)
    target_countries: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    generated_by: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    final_score: Mapped[float | None] = mapped_column(Float)
    maturity_level: Mapped[str | None] = mapped_column(String(64))
    error_reason: Mapped[str | None] = mapped_column(Text)
    output_word: Mapped[dict[str, Any] | None] = mapped_column(SQLiteJSON)
    output_ppt: Mapped[dict[str, Any] | None] = mapped_column(SQLiteJSON)
    output_excel: Mapped[dict[str, Any] | None] = mapped_column(SQLiteJSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(SQLiteJSON)


class OverseasPlanVersionORM(TimestampStatusMetadataMixin, Base):
    """Immutable generated/edited plan body versions."""

    __tablename__ = "overseas_plan_versions"

    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    generation_source: Mapped[str] = mapped_column(String(64), nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    generation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_final: Mapped[bool] = mapped_column(default=False, nullable=False)
    finalized_by: Mapped[str | None] = mapped_column(String(128))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OverseasAuditLogORM(TimestampStatusMetadataMixin, Base):
    """Append-only operation audit log."""

    __tablename__ = "overseas_audit_logs"

    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    username: Mapped[str | None] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    enterprise_id: Mapped[str | None] = mapped_column(String(64), index=True)
    plan_id: Mapped[str | None] = mapped_column(String(64), index=True)
    product_ids: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    target_countries: Mapped[list[str]] = mapped_column(SQLiteJSON, nullable=False, default=list)
    export_type: Mapped[str | None] = mapped_column(String(32))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    result_status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    version: Mapped[int | None] = mapped_column(Integer)
    generated_by: Mapped[str | None] = mapped_column(String(128))
    generated_at: Mapped[str | None] = mapped_column(String(64))
    success: Mapped[bool | None] = mapped_column()
    error_reason: Mapped[str | None] = mapped_column(Text)
    exported_by: Mapped[str | None] = mapped_column(String(128))
    exported_at: Mapped[str | None] = mapped_column(String(64))
    enterprise_name: Mapped[str | None] = mapped_column(String(255))
    plan_name: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(Text)


class ReportExportORM(TimestampStatusMetadataMixin, Base):
    """Exported report file records."""

    __tablename__ = "report_exports"

    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    export_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    exported_by: Mapped[str | None] = mapped_column(String(128))
    exported_at: Mapped[str | None] = mapped_column(String(64))
    plan_name: Mapped[str | None] = mapped_column(String(255))
