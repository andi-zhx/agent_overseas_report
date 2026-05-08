"""Repository abstractions and SQLAlchemy-backed implementations."""

from __future__ import annotations

import copy
from datetime import datetime
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
)
from agent_overseas_report.database.session import create_session_factory
from agent_overseas_report.models import GeneratedFileRef, GenerationProject, GenerationSource, GenerationStatus, MaturityLevel, PlanContentVersion
from agent_overseas_report.models.overseas_generation import utc_now
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


class EnterpriseRepository(Protocol):
    """Read/write port for enterprise and product master data."""

    def get_enterprise(self, enterprise_id: str) -> dict[str, Any]: ...

    def get_products(self, enterprise_id: str, product_ids: list[str]) -> list[dict[str, Any]]: ...

    def upsert_enterprise(self, enterprise: dict[str, Any]) -> dict[str, Any]: ...

    def upsert_product(self, product: dict[str, Any]) -> dict[str, Any]: ...


class SQLAlchemyEnterpriseRepository:
    """Enterprise/product repository backed by SQLAlchemy sessions."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @classmethod
    def from_engine(cls, engine: Engine) -> SQLAlchemyEnterpriseRepository:
        return cls(create_session_factory(engine))

    def upsert_enterprise(self, enterprise: dict[str, Any]) -> dict[str, Any]:
        enterprise_id = str(enterprise["id"])
        payload = copy.deepcopy(enterprise)
        now = utc_now()
        with self.session_factory() as session:
            row = session.get(EnterpriseORM, enterprise_id)
            if row is None:
                row = EnterpriseORM(
                    id=enterprise_id,
                    name=str(payload.get("name") or payload.get("enterprise_name") or enterprise_id),
                    industry=payload.get("industry"),
                    status=str(payload.get("status") or "active"),
                    metadata_=copy.deepcopy(payload.get("metadata", {})),
                    payload=payload,
                    created_at=_coerce_datetime(payload.get("created_at")) or now,
                    updated_at=_coerce_datetime(payload.get("updated_at")) or now,
                )
                session.add(row)
            else:
                row.name = str(payload.get("name") or payload.get("enterprise_name") or row.name)
                row.industry = payload.get("industry")
                row.status = str(payload.get("status") or row.status)
                row.metadata_ = copy.deepcopy(payload.get("metadata", row.metadata_ or {}))
                row.payload = payload
                row.updated_at = now
            session.commit()
        return copy.deepcopy(payload)

    def upsert_product(self, product: dict[str, Any]) -> dict[str, Any]:
        product_id = str(product["id"])
        payload = copy.deepcopy(product)
        now = utc_now()
        with self.session_factory() as session:
            row = session.get(ProductORM, product_id)
            if row is None:
                row = ProductORM(
                    id=product_id,
                    enterprise_id=str(payload["enterprise_id"]),
                    name=str(payload.get("name") or product_id),
                    status=str(payload.get("status") or "active"),
                    metadata_=copy.deepcopy(payload.get("metadata", {})),
                    payload=payload,
                    created_at=_coerce_datetime(payload.get("created_at")) or now,
                    updated_at=_coerce_datetime(payload.get("updated_at")) or now,
                )
                session.add(row)
            else:
                row.enterprise_id = str(payload["enterprise_id"])
                row.name = str(payload.get("name") or row.name)
                row.status = str(payload.get("status") or row.status)
                row.metadata_ = copy.deepcopy(payload.get("metadata", row.metadata_ or {}))
                row.payload = payload
                row.updated_at = now
            session.commit()
        return copy.deepcopy(payload)

    def get_enterprise(self, enterprise_id: str) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(EnterpriseORM, enterprise_id)
            if row is None:
                raise DataNotFoundError(f"Enterprise not found: {enterprise_id}")
            payload = copy.deepcopy(row.payload or {})
            payload.setdefault("id", row.id)
            payload.setdefault("name", row.name)
            payload.setdefault("industry", row.industry)
            return payload

    def get_products(self, enterprise_id: str, product_ids: list[str]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        with self.session_factory() as session:
            for product_id in product_ids:
                row = session.get(ProductORM, product_id)
                if row is None or row.enterprise_id != enterprise_id:
                    raise DataNotFoundError(f"Product not found for enterprise {enterprise_id}: {product_id}")
                payload = copy.deepcopy(row.payload or {})
                payload.setdefault("id", row.id)
                payload.setdefault("enterprise_id", row.enterprise_id)
                payload.setdefault("name", row.name)
                selected.append(payload)
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


def seed_demo_data(enterprise_repository: SQLAlchemyEnterpriseRepository) -> None:
    """Seed the same demo records that the in-memory API previously exposed."""

    enterprise_repository.upsert_enterprise(
        {
            "id": "ent-1",
            "name": "示例医疗科技",
            "industry": "医疗器械",
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
            "hs_code": "902780",
            "certifications": ["CE", "ISO 13485"],
            "capacity": {"monthly_units": 10000, "lead_time_days": 30},
            "moq": 50,
            "price_band": "USD 200-500",
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
        status=log.result_status,
        metadata_={"audit_log_id": log.id, "action_type": log.action_type},
    )


def _status_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
