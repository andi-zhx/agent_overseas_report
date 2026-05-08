"""Repository abstractions and SQLAlchemy-backed implementations."""

from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from agent_overseas_report.database.models import (
    EnterpriseORM,
    OverseasAuditLogORM,
    OverseasGenerationProjectORM,
    OverseasPlanVersionORM,
    ProductORM,
    ReportExportORM,
    ReportQualityScoreORM,
    WebResearchSourceORM,
)
from agent_overseas_report.database.session import create_session_factory
from agent_overseas_report.models import GeneratedFileRef, GenerationProject, GenerationSource, GenerationStatus, MaturityLevel, PlanContentVersion
from agent_overseas_report.models.overseas_generation import utc_now
from agent_overseas_report.services.web_research_service import WebResearchSource
from agent_overseas_report.services.report_quality_scoring_service import (
    ReportQualityDimensionScore,
    ReportQualityScore,
    ReportQualityStatus,
)
from agent_overseas_report.services.generation_service import (
    AuditLogQuery,
    DataNotFoundError,
    OverseasPlanAuditLog,
    _filter_audit_logs,
    _is_export_action,
)


class GenerationRepository(Protocol):
    """Port used by the generation service to persist projects, versions and audits."""

    def next_version(self, enterprise_id: str) -> int: ...

    def save_project(self, project: GenerationProject) -> GenerationProject: ...

    def get_plan_group_id(self, project_id: str) -> str | None: ...

    def next_content_version(self, project_id: str) -> int: ...

    def append_content_version(self, version: PlanContentVersion) -> PlanContentVersion: ...

    def list_content_versions(self, project_id: str) -> list[PlanContentVersion]: ...

    def get_content_version(self, project_id: str, version_number: int) -> PlanContentVersion | None: ...

    def mark_final_content_version(self, project_id: str, version_number: int, *, finalized_by: str | None) -> PlanContentVersion | None: ...

    def find_export_content_version(self, project_id: str) -> PlanContentVersion | None: ...

    def get_project(self, project_id: str) -> GenerationProject | None: ...

    def delete_project(self, project_id: str) -> GenerationProject | None: ...

    def append_audit_log(self, audit_log: OverseasPlanAuditLog) -> OverseasPlanAuditLog: ...

    def list_audit_logs(self, project_id: str | None = None, query: AuditLogQuery | None = None) -> list[OverseasPlanAuditLog]: ...

    def append_export_audit_log(self, audit_log: OverseasPlanAuditLog) -> OverseasPlanAuditLog: ...

    def list_export_audit_logs(self, project_id: str | None = None) -> list[OverseasPlanAuditLog]: ...

    def save_report_quality_score(self, score: ReportQualityScore) -> ReportQualityScore: ...

    def get_latest_report_quality_score(self, project_id: str) -> ReportQualityScore | None: ...


class EnterpriseRepository(Protocol):
    """Read/write port for enterprise and product master data."""

    def list_enterprises(self, *, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]: ...

    def get_enterprise(self, enterprise_id: str) -> dict[str, Any]: ...

    def get_products(self, enterprise_id: str, product_ids: list[str]) -> list[dict[str, Any]]: ...

    def list_products(self, enterprise_id: str | None = None, *, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]: ...

    def upsert_enterprise(self, enterprise: dict[str, Any]) -> dict[str, Any]: ...

    def delete_enterprise(self, enterprise_id: str) -> dict[str, Any] | None: ...

    def upsert_product(self, product: dict[str, Any]) -> dict[str, Any]: ...

    def delete_product(self, product_id: str) -> dict[str, Any] | None: ...


class SQLAlchemyEnterpriseRepository:
    """Enterprise/product repository backed by SQLAlchemy sessions."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @classmethod
    def from_engine(cls, engine: Engine) -> SQLAlchemyEnterpriseRepository:
        return cls(create_session_factory(engine))

    def list_enterprises(self, *, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.scalars(select(EnterpriseORM).order_by(EnterpriseORM.created_at.desc()).offset(offset).limit(limit)).all()
            return [_enterprise_row_to_payload(row) for row in rows]

    def upsert_enterprise(self, enterprise: dict[str, Any]) -> dict[str, Any]:
        enterprise_id = str(enterprise["id"])
        payload = copy.deepcopy(enterprise)
        now = utc_now()
        with self.session_factory() as session:
            row = session.get(EnterpriseORM, enterprise_id)
            if row is None:
                row = EnterpriseORM(id=enterprise_id, created_at=_coerce_datetime(payload.get("created_at")) or now)
                session.add(row)
            _apply_enterprise_payload(row, payload, now=now)
            session.commit()
            session.refresh(row)
            return _enterprise_row_to_payload(row)

    def delete_enterprise(self, enterprise_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(EnterpriseORM, enterprise_id)
            if row is None:
                return None
            payload = _enterprise_row_to_payload(row)
            session.delete(row)
            session.commit()
            return payload

    def list_products(self, enterprise_id: str | None = None, *, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        stmt = select(ProductORM).order_by(ProductORM.created_at.desc()).offset(offset).limit(limit)
        if enterprise_id is not None:
            stmt = stmt.where(ProductORM.enterprise_id == enterprise_id)
        with self.session_factory() as session:
            rows = session.scalars(stmt).all()
            return [_product_row_to_payload(row) for row in rows]

    def upsert_product(self, product: dict[str, Any]) -> dict[str, Any]:
        product_id = str(product["id"])
        payload = copy.deepcopy(product)
        now = utc_now()
        with self.session_factory() as session:
            enterprise_id = str(payload["enterprise_id"])
            if session.get(EnterpriseORM, enterprise_id) is None:
                raise DataNotFoundError(f"Enterprise not found: {enterprise_id}")
            row = session.get(ProductORM, product_id)
            if row is None:
                row = ProductORM(id=product_id, created_at=_coerce_datetime(payload.get("created_at")) or now)
                session.add(row)
            _apply_product_payload(row, payload, now=now)
            session.commit()
            session.refresh(row)
            return _product_row_to_payload(row)

    def delete_product(self, product_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(ProductORM, product_id)
            if row is None:
                return None
            payload = _product_row_to_payload(row)
            session.delete(row)
            session.commit()
            return payload

    def get_enterprise(self, enterprise_id: str) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(EnterpriseORM, enterprise_id)
            if row is None:
                raise DataNotFoundError(f"Enterprise not found: {enterprise_id}")
            return _enterprise_row_to_payload(row)

    def get_products(self, enterprise_id: str, product_ids: list[str]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        with self.session_factory() as session:
            for product_id in product_ids:
                row = session.get(ProductORM, product_id)
                if row is None or row.enterprise_id != enterprise_id:
                    raise DataNotFoundError(f"Product not found for enterprise {enterprise_id}: {product_id}")
                selected.append(_product_row_to_payload(row))
        return selected


class SQLiteGenerationRepository:
    """SQLite/SQLAlchemy implementation of the generation repository port."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @classmethod
    def from_engine(cls, engine: Engine) -> SQLiteGenerationRepository:
        return cls(create_session_factory(engine))

    def next_version(self, enterprise_id: str) -> int:
        with self.session_factory() as session:
            current = session.scalar(
                select(func.max(OverseasGenerationProjectORM.version)).where(
                    OverseasGenerationProjectORM.enterprise_id == enterprise_id
                )
            )
        return int(current or 0) + 1

    def save_project(self, project: GenerationProject) -> GenerationProject:
        project.updated_at = utc_now()
        project.metadata.setdefault("plan_group_id", project.id)
        payload = _project_to_payload(project)
        with self.session_factory() as session:
            row = session.get(OverseasGenerationProjectORM, project.id)
            if row is None:
                row = OverseasGenerationProjectORM(id=project.id, created_at=project.created_at)
                session.add(row)
            _apply_project_payload(row, payload)
            session.commit()
        return copy.deepcopy(project)

    def get_plan_group_id(self, project_id: str) -> str | None:
        project = self.get_project(project_id)
        if project is None:
            return None
        return str(project.metadata.get("plan_group_id") or project.id)

    def next_content_version(self, project_id: str) -> int:
        group_id = self.get_plan_group_id(project_id) or project_id
        with self.session_factory() as session:
            current = session.scalar(
                select(func.max(OverseasPlanVersionORM.version_number)).where(OverseasPlanVersionORM.project_id == group_id)
            )
        return int(current or 0) + 1

    def append_content_version(self, version: PlanContentVersion) -> PlanContentVersion:
        group_id = self.get_plan_group_id(version.project_id) or version.project_id
        saved = copy.deepcopy(version)
        saved.project_id = group_id
        if saved.id is None:
            saved.id = f"opv_{uuid4().hex}"
        with self.session_factory() as session:
            row = OverseasPlanVersionORM(
                id=saved.id,
                project_id=saved.project_id,
                source_project_id=saved.source_project_id,
                version_number=saved.version_number,
                created_by=saved.created_by,
                created_at=saved.created_at,
                updated_at=saved.created_at,
                status=_status_value(saved.generation_status),
                metadata_={},
                generation_source=_status_value(saved.generation_source),
                change_summary=saved.change_summary,
                content_json=copy.deepcopy(saved.content_json),
                generation_status=_status_value(saved.generation_status),
                is_final=saved.is_final,
                finalized_by=saved.finalized_by,
                finalized_at=saved.finalized_at,
            )
            session.add(row)
            session.commit()
        return saved

    def list_content_versions(self, project_id: str) -> list[PlanContentVersion]:
        group_id = self.get_plan_group_id(project_id) or project_id
        with self.session_factory() as session:
            rows = session.scalars(
                select(OverseasPlanVersionORM)
                .where(OverseasPlanVersionORM.project_id == group_id)
                .order_by(OverseasPlanVersionORM.version_number)
            ).all()
            return [_row_to_content_version(row) for row in rows]

    def get_content_version(self, project_id: str, version_number: int) -> PlanContentVersion | None:
        for version in self.list_content_versions(project_id):
            if version.version_number == version_number:
                return version
        return None

    def mark_final_content_version(self, project_id: str, version_number: int, *, finalized_by: str | None) -> PlanContentVersion | None:
        group_id = self.get_plan_group_id(project_id) or project_id
        now = utc_now()
        selected: OverseasPlanVersionORM | None = None
        with self.session_factory() as session:
            rows = session.scalars(select(OverseasPlanVersionORM).where(OverseasPlanVersionORM.project_id == group_id)).all()
            for row in rows:
                row.is_final = row.version_number == version_number
                row.updated_at = now
                if row.is_final:
                    row.finalized_by = finalized_by
                    row.finalized_at = now
                    selected = row
            session.commit()
            return _row_to_content_version(selected) if selected else None

    def find_export_content_version(self, project_id: str) -> PlanContentVersion | None:
        versions = [v for v in self.list_content_versions(project_id) if v.generation_status == GenerationStatus.COMPLETED]
        final_versions = [version for version in versions if version.is_final]
        if final_versions:
            return max(final_versions, key=lambda item: item.version_number)
        return max(versions, key=lambda item: item.version_number) if versions else None

    def get_project(self, project_id: str) -> GenerationProject | None:
        with self.session_factory() as session:
            row = session.get(OverseasGenerationProjectORM, project_id)
            return _row_to_project(row) if row else None

    def delete_project(self, project_id: str) -> GenerationProject | None:
        with self.session_factory() as session:
            row = session.get(OverseasGenerationProjectORM, project_id)
            if row is None:
                return None
            project = _row_to_project(row)
            session.delete(row)
            session.commit()
            return project

    def append_audit_log(self, audit_log: OverseasPlanAuditLog) -> OverseasPlanAuditLog:
        with self.session_factory() as session:
            session.add(_audit_log_to_row(audit_log))
            if _is_export_action(audit_log.action_type):
                session.add(_export_to_row(audit_log))
            session.commit()
        return copy.deepcopy(audit_log)

    def list_audit_logs(self, project_id: str | None = None, query: AuditLogQuery | None = None) -> list[OverseasPlanAuditLog]:
        with self.session_factory() as session:
            statement = select(OverseasAuditLogORM).order_by(OverseasAuditLogORM.created_at, OverseasAuditLogORM.id)
            rows = session.scalars(statement).all()
            logs = [_row_to_audit_log(row) for row in rows]
        if project_id is not None:
            logs = [log for log in logs if log.plan_id == project_id or log.project_id == project_id]
        if query is not None:
            logs = _filter_audit_logs(logs, query)
        return logs

    def append_export_audit_log(self, audit_log: OverseasPlanAuditLog) -> OverseasPlanAuditLog:
        return self.append_audit_log(audit_log)

    def list_export_audit_logs(self, project_id: str | None = None) -> list[OverseasPlanAuditLog]:
        logs = [log for log in self.list_audit_logs() if _is_export_action(log.action_type)]
        if project_id is not None:
            logs = [log for log in logs if log.plan_id == project_id or log.project_id == project_id]
        return logs

    def save_report_quality_score(self, score: ReportQualityScore) -> ReportQualityScore:
        saved = copy.deepcopy(score)
        if saved.id is None:
            saved.id = f"rqs_{uuid4().hex}"
        with self.session_factory() as session:
            session.add(_quality_score_to_row(saved))
            session.commit()
        return saved

    def get_latest_report_quality_score(self, project_id: str) -> ReportQualityScore | None:
        with self.session_factory() as session:
            row = session.scalars(
                select(ReportQualityScoreORM)
                .where(ReportQualityScoreORM.project_id == project_id)
                .order_by(ReportQualityScoreORM.created_at.desc(), ReportQualityScoreORM.id.desc())
                .limit(1)
            ).first()
            return _row_to_quality_score(row) if row else None

    def list_report_exports(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            statement = select(ReportExportORM).order_by(ReportExportORM.created_at, ReportExportORM.id)
            if project_id is not None:
                statement = statement.where(ReportExportORM.project_id == project_id)
            rows = session.scalars(statement).all()
            return [
                {
                    "id": row.id,
                    "project_id": row.project_id,
                    "export_type": row.export_type,
                    "file_path": row.file_path,
                    "exported_by": row.exported_by,
                    "exported_at": row.exported_at,
                    "plan_name": row.plan_name,
                    "status": row.status,
                    "metadata": copy.deepcopy(row.metadata_ or {}),
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in rows
            ]



class SQLiteWebResearchSourceRepository:
    """SQLite/SQLAlchemy repository for source-preserving web research records."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @classmethod
    def from_engine(cls, engine: Engine) -> SQLiteWebResearchSourceRepository:
        return cls(create_session_factory(engine))

    def save_sources(self, sources: list[WebResearchSource]) -> list[WebResearchSource]:
        saved: list[WebResearchSource] = []
        with self.session_factory() as session:
            for source in sources:
                existing = session.scalar(
                    select(WebResearchSourceORM).where(
                        WebResearchSourceORM.query == source.query,
                        WebResearchSourceORM.url == source.url,
                    )
                )
                row = existing or WebResearchSourceORM(id=source.id, created_at=_coerce_datetime(source.retrieved_at) or utc_now())
                if existing is None:
                    session.add(row)
                _apply_web_research_source(row, source)
                saved.append(_web_research_row_to_source(row))
            session.commit()
        return saved

    def find_cached_sources(
        self,
        *,
        query: str,
        related_enterprise_id: str | None = None,
        related_product_id: str | None = None,
        related_country: str | None = None,
        related_industry: str | None = None,
        min_retrieved_at: datetime | None = None,
    ) -> list[WebResearchSource]:
        statement = select(WebResearchSourceORM).where(WebResearchSourceORM.query == query)
        if related_enterprise_id is not None:
            statement = statement.where(WebResearchSourceORM.related_enterprise_id == related_enterprise_id)
        if related_product_id is not None:
            statement = statement.where(WebResearchSourceORM.related_product_id == related_product_id)
        if related_country is not None:
            statement = statement.where(WebResearchSourceORM.related_country == related_country)
        if related_industry is not None:
            statement = statement.where(WebResearchSourceORM.related_industry == related_industry)
        if min_retrieved_at is not None:
            statement = statement.where(WebResearchSourceORM.retrieved_at >= min_retrieved_at)
        statement = statement.order_by(WebResearchSourceORM.reliability_score.desc(), WebResearchSourceORM.retrieved_at.desc())
        with self.session_factory() as session:
            return [_web_research_row_to_source(row) for row in session.scalars(statement).all()]


ENTERPRISE_STRUCTURED_FIELDS = {
    "name",
    "unified_social_credit_code",
    "industry",
    "enterprise_nature",
    "established_at",
    "region",
    "main_business",
    "core_products",
    "annual_revenue_range",
    "export_experience",
    "current_export_countries",
    "capacity_status",
    "certifications",
    "financing_needs",
    "overseas_goals",
    "investment_profile",
    "market_entry_preferences",
    "channel_requirements",
    "expansion_plan",
}

PRODUCT_STRUCTURED_FIELDS = {
    "enterprise_id",
    "name",
    "product_category",
    "hs_code",
    "application_scenarios",
    "core_selling_points",
    "technical_parameters",
    "price_range",
    "moq",
    "capacity",
    "certifications",
    "target_customers",
    "competitors",
    "export_restrictions",
    "compliance_requirements",
    "investment_highlights",
    "market_entry_notes",
    "channel_fit",
    "financing_expansion_assumptions",
}


def _apply_web_research_source(row: WebResearchSourceORM, source: WebResearchSource) -> None:
    retrieved_at = _coerce_datetime(source.retrieved_at) or utc_now()
    row.query = source.query
    row.title = source.title
    row.url = source.url
    row.snippet = source.snippet
    row.source_domain = source.source_domain
    row.publish_date = _coerce_date(source.publish_date)
    row.retrieved_at = retrieved_at
    row.reliability_score = float(source.reliability_score)
    row.source_type = source.source_type
    row.related_enterprise_id = source.related_enterprise_id
    row.related_product_id = source.related_product_id
    row.related_country = source.related_country
    row.related_industry = source.related_industry
    row.status = "active"
    row.metadata_ = copy.deepcopy(source.metadata or {})
    row.updated_at = retrieved_at


def _web_research_row_to_source(row: WebResearchSourceORM) -> WebResearchSource:
    return WebResearchSource(
        id=row.id,
        query=row.query,
        title=row.title,
        url=row.url,
        snippet=row.snippet,
        source_domain=row.source_domain,
        publish_date=row.publish_date,
        retrieved_at=row.retrieved_at,
        reliability_score=row.reliability_score,
        source_type=row.source_type,
        related_enterprise_id=row.related_enterprise_id,
        related_product_id=row.related_product_id,
        related_country=row.related_country,
        related_industry=row.related_industry,
        metadata=copy.deepcopy(row.metadata_ or {}),
    )


def _apply_enterprise_payload(row: EnterpriseORM, payload: dict[str, Any], *, now: datetime) -> None:
    row.name = str(payload.get("name") or payload.get("enterprise_name") or row.id)
    row.unified_social_credit_code = payload.get("unified_social_credit_code")
    row.industry = payload.get("industry")
    row.enterprise_nature = payload.get("enterprise_nature")
    row.established_at = _coerce_date(payload.get("established_at"))
    row.region = payload.get("region")
    row.main_business = payload.get("main_business")
    row.core_products = _list_value(payload.get("core_products"))
    row.annual_revenue_range = payload.get("annual_revenue_range")
    row.export_experience = payload.get("export_experience")
    row.current_export_countries = _list_value(payload.get("current_export_countries"))
    row.capacity_status = _dict_value(payload.get("capacity_status"))
    row.certifications = _list_value(payload.get("certifications"))
    row.financing_needs = _dict_value(payload.get("financing_needs"))
    row.overseas_goals = _list_value(payload.get("overseas_goals"))
    row.investment_profile = _dict_value(payload.get("investment_profile"))
    row.market_entry_preferences = _dict_value(payload.get("market_entry_preferences"))
    row.channel_requirements = _dict_value(payload.get("channel_requirements"))
    row.expansion_plan = _dict_value(payload.get("expansion_plan"))
    row.status = str(payload.get("status") or row.status or "active")
    row.metadata_ = copy.deepcopy(payload.get("metadata", row.metadata_ or {}))
    row.payload = copy.deepcopy(payload)
    row.updated_at = _coerce_datetime(payload.get("updated_at")) or now


def _apply_product_payload(row: ProductORM, payload: dict[str, Any], *, now: datetime) -> None:
    row.enterprise_id = str(payload["enterprise_id"])
    row.name = str(payload.get("name") or row.id)
    row.product_category = payload.get("product_category")
    row.hs_code = payload.get("hs_code")
    row.application_scenarios = _list_value(payload.get("application_scenarios"))
    row.core_selling_points = _list_value(payload.get("core_selling_points"))
    row.technical_parameters = _dict_value(payload.get("technical_parameters"))
    row.price_range = payload.get("price_range") or payload.get("price_band")
    row.moq = str(payload.get("moq")) if payload.get("moq") is not None else None
    row.capacity = _dict_value(payload.get("capacity"))
    row.certifications = _list_value(payload.get("certifications"))
    row.target_customers = _list_value(payload.get("target_customers"))
    row.competitors = _list_value(payload.get("competitors"))
    row.export_restrictions = payload.get("export_restrictions")
    row.compliance_requirements = _list_value(payload.get("compliance_requirements"))
    row.investment_highlights = _list_value(payload.get("investment_highlights"))
    row.market_entry_notes = _dict_value(payload.get("market_entry_notes"))
    row.channel_fit = _dict_value(payload.get("channel_fit"))
    row.financing_expansion_assumptions = _dict_value(payload.get("financing_expansion_assumptions"))
    row.status = str(payload.get("status") or row.status or "active")
    row.metadata_ = copy.deepcopy(payload.get("metadata", row.metadata_ or {}))
    row.payload = copy.deepcopy(payload)
    row.updated_at = _coerce_datetime(payload.get("updated_at")) or now


def _enterprise_row_to_payload(row: EnterpriseORM) -> dict[str, Any]:
    payload = copy.deepcopy(row.payload or {})
    payload.update(
        {
            "id": row.id,
            "name": row.name,
            "unified_social_credit_code": row.unified_social_credit_code,
            "industry": row.industry,
            "enterprise_nature": row.enterprise_nature,
            "established_at": row.established_at.isoformat() if row.established_at else payload.get("established_at"),
            "region": row.region,
            "main_business": row.main_business,
            "core_products": copy.deepcopy(row.core_products or []),
            "annual_revenue_range": row.annual_revenue_range,
            "export_experience": row.export_experience,
            "current_export_countries": copy.deepcopy(row.current_export_countries or []),
            "capacity_status": copy.deepcopy(row.capacity_status or {}),
            "certifications": copy.deepcopy(row.certifications or []),
            "financing_needs": copy.deepcopy(row.financing_needs or {}),
            "overseas_goals": copy.deepcopy(row.overseas_goals or []),
            "investment_profile": copy.deepcopy(row.investment_profile or {}),
            "market_entry_preferences": copy.deepcopy(row.market_entry_preferences or {}),
            "channel_requirements": copy.deepcopy(row.channel_requirements or {}),
            "expansion_plan": copy.deepcopy(row.expansion_plan or {}),
            "metadata": copy.deepcopy(row.metadata_ or {}),
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    )
    return payload


def _product_row_to_payload(row: ProductORM) -> dict[str, Any]:
    payload = copy.deepcopy(row.payload or {})
    payload.update(
        {
            "id": row.id,
            "enterprise_id": row.enterprise_id,
            "name": row.name,
            "product_category": row.product_category,
            "hs_code": row.hs_code,
            "application_scenarios": copy.deepcopy(row.application_scenarios or []),
            "core_selling_points": copy.deepcopy(row.core_selling_points or []),
            "technical_parameters": copy.deepcopy(row.technical_parameters or {}),
            "price_range": row.price_range,
            "moq": row.moq,
            "capacity": copy.deepcopy(row.capacity or {}),
            "certifications": copy.deepcopy(row.certifications or []),
            "target_customers": copy.deepcopy(row.target_customers or []),
            "competitors": copy.deepcopy(row.competitors or []),
            "export_restrictions": row.export_restrictions,
            "compliance_requirements": copy.deepcopy(row.compliance_requirements or []),
            "investment_highlights": copy.deepcopy(row.investment_highlights or []),
            "market_entry_notes": copy.deepcopy(row.market_entry_notes or {}),
            "channel_fit": copy.deepcopy(row.channel_fit or {}),
            "financing_expansion_assumptions": copy.deepcopy(row.financing_expansion_assumptions or {}),
            "metadata": copy.deepcopy(row.metadata_ or {}),
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    )
    return payload


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return copy.deepcopy(value)
    return [value]


def _dict_value(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}

def seed_demo_data(enterprise_repository: SQLAlchemyEnterpriseRepository) -> None:
    """Seed the same demo records that the in-memory API previously exposed."""

    enterprise_repository.upsert_enterprise(
        {
            "id": "ent-1",
            "name": "示例医疗科技",
            "industry": "医疗器械",
            "unified_social_credit_code": "91310000MA1K000000",
            "enterprise_nature": "民营企业",
            "established_at": "2018-06-01",
            "region": "上海市",
            "main_business": "便携式医疗检测设备研发、生产与销售",
            "core_products": ["便携式检测仪"],
            "annual_revenue_range": "5000万-1亿元",
            "export_experience": "已有2年欧洲经销出口经验",
            "current_export_countries": ["德国"],
            "capacity_status": {"monthly_units": 10000, "utilization_rate": "70%"},
            "certifications": ["CE", "ISO 13485"],
            "financing_needs": {"amount": 5000000, "purpose": "扩建海外版产线"},
            "overseas_goals": ["拓展欧盟渠道", "建立本地售后伙伴"],
            "investment_profile": {"gross_margin": "35%", "growth_stage": "成长期"},
            "market_entry_preferences": {"priority_regions": ["欧盟"], "entry_modes": ["经销商"]},
            "channel_requirements": {"partner_types": ["医疗器械经销商", "本地售后服务商"]},
            "expansion_plan": {"new_monthly_capacity": 20000, "capex": 8000000},
            "overseas_customers": ["德国经销商A"],
            "english_materials": ["英文官网", "英文说明书"],
            "team": {"international_members": 3, "languages": ["英语", "德语"], "export_years": 2},
            "finance": {"export_budget": 800000, "credit_line": 1200000},
            "metadata": {"seeded": True},
        }
    )
    enterprise_repository.upsert_product(
        {
            "id": "prod-1",
            "enterprise_id": "ent-1",
            "name": "便携式检测仪",
            "product_category": "医疗检测设备",
            "hs_code": "902780",
            "application_scenarios": ["基层医疗", "移动检测", "海外诊所"],
            "core_selling_points": ["便携", "检测速度快", "支持多语言界面"],
            "technical_parameters": {"battery_life_hours": 8, "languages": ["英语", "德语"]},
            "price_range": "USD 200-500",
            "certifications": ["CE", "ISO 13485"],
            "capacity": {"monthly_units": 10000, "lead_time_days": 30},
            "moq": 50,
            "price_band": "USD 200-500",
            "target_customers": ["海外诊所", "医疗器械经销商"],
            "competitors": ["国际便携检测设备品牌"],
            "export_restrictions": "需满足目标国医疗器械注册要求",
            "compliance_requirements": ["CE MDR", "当地医疗器械注册"],
            "investment_highlights": ["耗材复购", "轻量化交付"],
            "market_entry_notes": {"recommended_mode": "经销商+售后服务伙伴"},
            "channel_fit": {"preferred_channels": ["医疗器械经销商", "行业展会"]},
            "financing_expansion_assumptions": {"capacity_after_financing": {"monthly_units": 20000}},
            "overseas_version": True,
            "metadata": {"seeded": True},
        }
    )


def _project_to_payload(project: GenerationProject) -> dict[str, Any]:
    return project.to_dict()


def _apply_project_payload(row: OverseasGenerationProjectORM, payload: dict[str, Any]) -> None:
    row.enterprise_id = payload["enterprise_id"]
    row.product_ids = copy.deepcopy(payload.get("product_ids", []))
    row.selected_industry = payload["selected_industry"]
    row.target_countries = copy.deepcopy(payload.get("target_countries", []))
    row.status = payload.get("generation_status") or payload.get("status") or "draft"
    row.metadata_ = copy.deepcopy(payload.get("metadata", {}))
    row.generated_by = payload.get("generated_by")
    row.created_at = _coerce_datetime(payload.get("created_at")) or row.created_at or utc_now()
    row.updated_at = _coerce_datetime(payload.get("updated_at")) or utc_now()
    row.version = int(payload.get("version") or 1)
    row.final_score = payload.get("final_score")
    row.maturity_level = payload.get("maturity_level")
    row.error_reason = payload.get("error_reason")
    row.output_word = copy.deepcopy(payload.get("output_word"))
    row.output_ppt = copy.deepcopy(payload.get("output_ppt"))
    row.output_excel = copy.deepcopy(payload.get("output_excel"))
    row.result = copy.deepcopy(payload.get("result"))


def _row_to_project(row: OverseasGenerationProjectORM) -> GenerationProject:
    return GenerationProject(
        id=row.id,
        enterprise_id=row.enterprise_id,
        product_ids=copy.deepcopy(row.product_ids or []),
        selected_industry=row.selected_industry,
        target_countries=copy.deepcopy(row.target_countries or []),
        generation_status=GenerationStatus(row.status),
        generated_by=row.generated_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
        final_score=row.final_score,
        maturity_level=MaturityLevel(row.maturity_level) if row.maturity_level else None,
        error_reason=row.error_reason,
        output_word=_file_ref(row.output_word),
        output_ppt=_file_ref(row.output_ppt),
        output_excel=_file_ref(row.output_excel),
        result=copy.deepcopy(row.result),
        metadata=copy.deepcopy(row.metadata_ or {}),
    )


def _file_ref(payload: dict[str, Any] | None) -> GeneratedFileRef | None:
    return GeneratedFileRef(**payload) if payload else None


def _row_to_content_version(row: OverseasPlanVersionORM) -> PlanContentVersion:
    return PlanContentVersion(
        id=row.id,
        project_id=row.project_id,
        source_project_id=row.source_project_id,
        version_number=row.version_number,
        created_by=row.created_by,
        created_at=row.created_at,
        generation_source=GenerationSource(row.generation_source),
        change_summary=row.change_summary,
        content_json=copy.deepcopy(row.content_json or {}),
        generation_status=GenerationStatus(row.generation_status),
        is_final=row.is_final,
        finalized_by=row.finalized_by,
        finalized_at=row.finalized_at,
    )


def _audit_log_to_row(log: OverseasPlanAuditLog) -> OverseasAuditLogORM:
    return OverseasAuditLogORM(
        id=log.id,
        created_at=_coerce_datetime(log.created_at) or utc_now(),
        updated_at=_coerce_datetime(log.created_at) or utc_now(),
        status=log.result_status,
        metadata_=copy.deepcopy(log.metadata or {}),
        user_id=log.user_id,
        username=log.username,
        action_type=log.action_type,
        enterprise_id=log.enterprise_id,
        plan_id=log.plan_id,
        product_ids=copy.deepcopy(log.product_ids),
        target_countries=copy.deepcopy(log.target_countries),
        export_type=log.export_type,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        result_status=log.result_status,
        error_message=log.error_message,
        project_id=log.project_id,
        version=log.version,
        generated_by=log.generated_by,
        generated_at=log.generated_at,
        success=log.success,
        error_reason=log.error_reason,
        exported_by=log.exported_by,
        exported_at=log.exported_at,
        enterprise_name=log.enterprise_name,
        plan_name=log.plan_name,
        file_path=log.file_path,
        used_enterprise_data=copy.deepcopy(log.used_enterprise_data),
        used_product_data=copy.deepcopy(log.used_product_data),
        used_local_knowledge_files=copy.deepcopy(log.used_local_knowledge_files),
        web_research_enabled=log.web_research_enabled,
        external_sources=copy.deepcopy(log.external_sources),
        edited_by=log.edited_by,
        finalized_by=log.finalized_by,
        export_audience=log.export_audience,
    )


def _row_to_audit_log(row: OverseasAuditLogORM) -> OverseasPlanAuditLog:
    return OverseasPlanAuditLog(
        id=row.id,
        user_id=row.user_id,
        username=row.username,
        action_type=row.action_type,
        enterprise_id=row.enterprise_id,
        plan_id=row.plan_id,
        product_ids=copy.deepcopy(row.product_ids or []),
        target_countries=copy.deepcopy(row.target_countries or []),
        export_type=row.export_type,
        created_at=row.created_at.isoformat(),
        ip_address=row.ip_address,
        user_agent=row.user_agent,
        result_status=row.result_status,
        error_message=row.error_message,
        metadata=copy.deepcopy(row.metadata_ or {}),
        used_enterprise_data=copy.deepcopy(row.used_enterprise_data or []),
        used_product_data=copy.deepcopy(row.used_product_data or []),
        used_local_knowledge_files=copy.deepcopy(row.used_local_knowledge_files or []),
        web_research_enabled=row.web_research_enabled,
        external_sources=copy.deepcopy(row.external_sources or []),
        edited_by=row.edited_by,
        finalized_by=row.finalized_by,
        export_audience=row.export_audience,
        project_id=row.project_id,
        version=row.version,
        generated_by=row.generated_by,
        generated_at=row.generated_at,
        success=row.success,
        error_reason=row.error_reason,
        exported_by=row.exported_by,
        exported_at=row.exported_at,
        enterprise_name=row.enterprise_name,
        plan_name=row.plan_name,
        file_path=row.file_path,
    )


def _export_to_row(log: OverseasPlanAuditLog) -> ReportExportORM:
    return ReportExportORM(
        id=f"rpt_{uuid4().hex}",
        project_id=log.plan_id or log.project_id or "",
        export_type=log.export_type or log.action_type,
        file_path=log.file_path,
        exported_by=log.exported_by or log.user_id,
        exported_at=log.exported_at or log.created_at,
        plan_name=log.plan_name,
        export_audience=log.export_audience,
        status=log.result_status,
        metadata_={"audit_log_id": log.id, "action_type": log.action_type, **copy.deepcopy(log.metadata or {})},
    )


def _status_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _quality_score_to_row(score: ReportQualityScore) -> ReportQualityScoreORM:
    return ReportQualityScoreORM(
        id=score.id or f"rqs_{uuid4().hex}",
        created_at=_coerce_datetime(score.created_at) or utc_now(),
        updated_at=_coerce_datetime(score.created_at) or utc_now(),
        status=score.status.value,
        metadata_=copy.deepcopy(score.metadata or {}),
        project_id=score.project_id,
        version_number=score.version_number,
        total_score=score.total_score,
        quality_status=score.status.value,
        dimension_scores=[asdict(item) for item in score.dimension_scores],
        issues=copy.deepcopy(score.issues),
        suggestions=copy.deepcopy(score.suggestions),
    )


def _row_to_quality_score(row: ReportQualityScoreORM) -> ReportQualityScore:
    return ReportQualityScore(
        id=row.id,
        project_id=row.project_id,
        version_number=row.version_number,
        total_score=row.total_score,
        status=ReportQualityStatus(row.quality_status),
        dimension_scores=[ReportQualityDimensionScore(**item) for item in copy.deepcopy(row.dimension_scores or [])],
        issues=copy.deepcopy(row.issues or []),
        suggestions=copy.deepcopy(row.suggestions or []),
        created_at=row.created_at,
        metadata=copy.deepcopy(row.metadata_ or {}),
    )
