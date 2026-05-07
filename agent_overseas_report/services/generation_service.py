"""Main orchestration service for enterprise overseas-plan generation.

The service is intentionally framework-agnostic: API handlers, CLI jobs or a
future async queue can all call ``create_generation`` and ``run_generation``.
For the current synchronous implementation ``generate`` executes the job inline
while still persisting explicit task status, errors, versions and audit logs.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

from agent_overseas_report.knowledge_base.repository import KnowledgeBaseTemplateRepository, get_default_template_repository
from agent_overseas_report.models import (
    GeneratedFileRef,
    GenerationProject,
    GenerationSource,
    GenerationStatus,
    MaturityLevel,
    PlanContentVersion,
)
from agent_overseas_report.models.overseas_generation import utc_now
from agent_overseas_report.prompts import build_overseas_plan_prompts
from agent_overseas_report.services.llm_service import LLMServiceError
from agent_overseas_report.services.generation_readiness import assess_generation_readiness
from agent_overseas_report.services.rule_engine import OverseasRuleEngine
from agent_overseas_report.services.excel_export_service import ExcelExportRequest, ExcelExportResult, export_overseas_plan_excel
from agent_overseas_report.services.ppt_export_service import PPTExportRequest, PPTExportResult, export_overseas_plan_ppt
from agent_overseas_report.services.word_export_service import WordExportRequest, WordExportResult, export_overseas_plan_word


class GenerationServiceError(RuntimeError):
    """Base exception for generation orchestration failures."""


class DataNotFoundError(GenerationServiceError):
    """Raised when requested enterprise or product data does not exist."""


class GenerationValidationError(GenerationServiceError):
    """Raised when model output cannot satisfy the plan JSON contract."""


class EnterpriseDataRepository(Protocol):
    """Read-only port for enterprise/product facts owned by upstream modules."""

    def get_enterprise(self, enterprise_id: str) -> dict[str, Any]:
        """Return enterprise base information by ID."""

    def get_products(self, enterprise_id: str, product_ids: list[str]) -> list[dict[str, Any]]:
        """Return selected products for an enterprise."""


class PlanLLMClient(Protocol):
    """Minimal LLM port used by the orchestration service."""

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text from an LLM provider."""


@dataclass(slots=True)
class RequestAuditContext:
    """Optional HTTP/user context supplied by API handlers for audit logs."""

    user_id: str | None = None
    username: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(slots=True)
class GenerationRequest:
    """Input DTO for creating a new overseas-plan generation version."""

    enterprise_id: str
    product_ids: list[str]
    selected_industry: str
    target_countries: list[str]
    generated_by: str
    project_id: str | None = None
    extra_context: dict[str, Any] = field(default_factory=dict)
    continue_on_validation_warning: bool = False
    username: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class OverseasPlanAuditAction:
    """Stable audit action codes reserved for backend/API integrations."""

    CREATE_PLAN = "create_plan"
    AI_GENERATE_PLAN = "ai_generate_plan"
    REGENERATE_PLAN = "regenerate_plan"
    VIEW_PLAN_DETAIL = "view_plan_detail"
    EDIT_AI_CONTENT = "edit_ai_content"
    EXPORT_WORD = "export_word"
    EXPORT_PPT = "export_ppt"
    EXPORT_EXCEL_ACTION_PLAN = "export_excel_action_plan"
    EXPORT_RESOURCE_LIST = "export_resource_list"
    RESTORE_VERSION = "restore_version"
    MARK_FINAL_VERSION = "mark_final_version"
    ARCHIVE_PLAN = "archive_plan"
    DELETE_PLAN = "delete_plan"


class AuditResultStatus:
    """Result status values for audit records."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(slots=True)
class OverseasPlanAuditLog:
    """Append-only audit record for overseas-plan operations.

    The log stores identifiers and operational metadata only. Generated AI body
    content is intentionally excluded to prevent sensitive report text from
    entering audit storage.
    """

    id: str
    user_id: str | None
    username: str | None
    action_type: str
    enterprise_id: str | None
    plan_id: str | None
    product_ids: list[str]
    target_countries: list[str]
    export_type: str | None
    created_at: str
    ip_address: str | None
    user_agent: str | None
    result_status: str
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Backward-compatible fields used by existing generation/export callers.
    project_id: str | None = None
    version: int | None = None
    generated_by: str | None = None
    generated_at: str | None = None
    success: bool | None = None
    error_reason: str | None = None
    exported_by: str | None = None
    exported_at: str | None = None
    enterprise_name: str | None = None
    plan_name: str | None = None
    file_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable audit-log payload."""

        return asdict(self)


@dataclass(slots=True)
class AuditLogQuery:
    """Filter object reserved for backend audit-log query endpoints."""

    enterprise_id: str | None = None
    user_id: str | None = None
    username: str | None = None
    action_type: str | None = None
    created_from: str | datetime | None = None
    created_to: str | datetime | None = None
    plan_id: str | None = None


GenerationAuditLog = OverseasPlanAuditLog
ExportAuditLog = OverseasPlanAuditLog


@dataclass(slots=True)
class GenerationPreviewResponse:
    """Frontend preview payload returned after a generation run."""

    project: dict[str, Any]
    preview: dict[str, Any] | None
    audit_log: dict[str, Any]


@dataclass(slots=True)
class PlanVersionListResponse:
    """Version history payload for frontend preview switching."""

    project_id: str
    current_version_number: int | None
    final_version_number: int | None
    versions: list[dict[str, Any]]


class InMemoryEnterpriseDataRepository:
    """Small adapter for tests/demos until real enterprise/product tables exist."""

    def __init__(self, enterprises: dict[str, dict[str, Any]], products: dict[str, dict[str, Any]]) -> None:
        self.enterprises = enterprises
        self.products = products

    def get_enterprise(self, enterprise_id: str) -> dict[str, Any]:
        try:
            return copy.deepcopy(self.enterprises[enterprise_id])
        except KeyError as exc:
            raise DataNotFoundError(f"Enterprise not found: {enterprise_id}") from exc

    def get_products(self, enterprise_id: str, product_ids: list[str]) -> list[dict[str, Any]]:
        selected = []
        for product_id in product_ids:
            product = self.products.get(product_id)
            if product is None or product.get("enterprise_id") != enterprise_id:
                raise DataNotFoundError(f"Product not found for enterprise {enterprise_id}: {product_id}")
            selected.append(copy.deepcopy(product))
        return selected


class InMemoryGenerationStore:
    """Versioned plan store with append-only audit logs.

    The interface mirrors operations expected from a future database repository:
    save project, find latest version, and append/query audit logs.
    """

    def __init__(self) -> None:
        self._projects: dict[str, GenerationProject] = {}
        self._versions: dict[str, list[PlanContentVersion]] = {}
        self._audit_logs: list[OverseasPlanAuditLog] = []

    def next_version(self, enterprise_id: str) -> int:
        versions = [project.version for project in self._projects.values() if project.enterprise_id == enterprise_id]
        return max(versions, default=0) + 1

    def save_project(self, project: GenerationProject) -> GenerationProject:
        project.updated_at = utc_now()
        project.metadata.setdefault("plan_group_id", project.id)
        self._projects[project.id] = copy.deepcopy(project)
        return project

    def get_plan_group_id(self, project_id: str) -> str | None:
        project = self._projects.get(project_id)
        if project is None:
            return None
        return str(project.metadata.get("plan_group_id") or project.id)

    def next_content_version(self, project_id: str) -> int:
        group_id = self.get_plan_group_id(project_id) or project_id
        versions = self._versions.get(group_id, [])
        return max((version.version_number for version in versions), default=0) + 1

    def append_content_version(self, version: PlanContentVersion) -> PlanContentVersion:
        group_id = self.get_plan_group_id(version.project_id) or version.project_id
        version.project_id = group_id
        if version.id is None:
            version.id = f"opv_{uuid4().hex}"
        self._versions.setdefault(group_id, []).append(copy.deepcopy(version))
        return copy.deepcopy(version)

    def list_content_versions(self, project_id: str) -> list[PlanContentVersion]:
        group_id = self.get_plan_group_id(project_id) or project_id
        versions = sorted(self._versions.get(group_id, []), key=lambda item: item.version_number)
        return copy.deepcopy(versions)

    def get_content_version(self, project_id: str, version_number: int) -> PlanContentVersion | None:
        for version in self.list_content_versions(project_id):
            if version.version_number == version_number:
                return version
        return None

    def mark_final_content_version(self, project_id: str, version_number: int, *, finalized_by: str | None) -> PlanContentVersion | None:
        group_id = self.get_plan_group_id(project_id) or project_id
        selected: PlanContentVersion | None = None
        versions = self._versions.get(group_id, [])
        now = utc_now()
        for version in versions:
            version.is_final = version.version_number == version_number
            if version.is_final:
                version.finalized_by = finalized_by
                version.finalized_at = now
                selected = copy.deepcopy(version)
        return selected

    def find_export_content_version(self, project_id: str) -> PlanContentVersion | None:
        versions = [v for v in self.list_content_versions(project_id) if v.generation_status == GenerationStatus.COMPLETED]
        final_versions = [version for version in versions if version.is_final]
        if final_versions:
            return max(final_versions, key=lambda item: item.version_number)
        return max(versions, key=lambda item: item.version_number) if versions else None

    def get_project(self, project_id: str) -> GenerationProject | None:
        project = self._projects.get(project_id)
        return copy.deepcopy(project) if project else None

    def delete_project(self, project_id: str) -> GenerationProject | None:
        project = self._projects.pop(project_id, None)
        return copy.deepcopy(project) if project else None

    def append_audit_log(self, audit_log: OverseasPlanAuditLog) -> OverseasPlanAuditLog:
        self._audit_logs.append(copy.deepcopy(audit_log))
        return audit_log

    def list_audit_logs(
        self,
        project_id: str | None = None,
        query: AuditLogQuery | None = None,
    ) -> list[OverseasPlanAuditLog]:
        logs = self._audit_logs
        if project_id is not None:
            logs = [log for log in logs if log.plan_id == project_id or log.project_id == project_id]
        if query is not None:
            logs = _filter_audit_logs(logs, query)
        return copy.deepcopy(logs)

    def append_export_audit_log(self, audit_log: OverseasPlanAuditLog) -> OverseasPlanAuditLog:
        return self.append_audit_log(audit_log)

    def list_export_audit_logs(self, project_id: str | None = None) -> list[OverseasPlanAuditLog]:
        logs = [log for log in self._audit_logs if _is_export_action(log.action_type)]
        if project_id is not None:
            logs = [log for log in logs if log.plan_id == project_id or log.project_id == project_id]
        return copy.deepcopy(logs)


@dataclass(slots=True)
class OverseasPlanGenerationService:
    """Main workflow service for generating structured overseas plans."""

    data_repository: EnterpriseDataRepository
    llm_client: PlanLLMClient
    store: InMemoryGenerationStore = field(default_factory=InMemoryGenerationStore)
    template_repository: KnowledgeBaseTemplateRepository = field(default_factory=get_default_template_repository)
    rule_engine: OverseasRuleEngine | None = None

    def __post_init__(self) -> None:
        if self.rule_engine is None:
            self.rule_engine = OverseasRuleEngine(repository=self.template_repository)

    def generate(self, request: GenerationRequest) -> GenerationPreviewResponse:
        """Create a new version and run generation inline.

        This method is deliberately a thin composition of ``create_generation``
        and ``run_generation`` so API handlers can later enqueue ``run_generation``
        in Celery/RQ/Arq without changing business logic.
        """

        project = self.create_generation(request)
        return self.run_generation(project.id, audit_context=_context_from_generation_request(request))

    def regenerate(
        self,
        project_id: str,
        *,
        generated_by: str,
        extra_context: dict[str, Any] | None = None,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationPreviewResponse:
        """Generate a new version from a historical project without overwriting it."""

        previous = self.store.get_project(project_id)
        if previous is None:
            self._write_audit_log(
                action_type=OverseasPlanAuditAction.REGENERATE_PLAN,
                user_id=generated_by,
                username=username,
                enterprise_id=None,
                plan_id=project_id,
                product_ids=[],
                target_countries=[],
                result_status=AuditResultStatus.FAILED,
                error_message=f"Generation project not found: {project_id}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise DataNotFoundError(f"Generation project not found: {project_id}")
        self._write_project_audit_log(
            previous,
            action_type=OverseasPlanAuditAction.REGENERATE_PLAN,
            user_id=generated_by,
            username=username,
            result_status=AuditResultStatus.SUCCESS,
            metadata={"regenerated_from_project_id": project_id},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        request = GenerationRequest(
            enterprise_id=previous.enterprise_id,
            product_ids=previous.product_ids,
            selected_industry=previous.selected_industry,
            target_countries=previous.target_countries,
            generated_by=generated_by,
            extra_context={
                "plan_group_id": previous.metadata.get("plan_group_id") or previous.id,
                "regenerated_from_project_id": project_id,
                "generation_source": GenerationSource.REGENERATED.value,
                **(extra_context or {}),
            },
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return self.generate(request)

    def create_generation(self, request: GenerationRequest) -> GenerationProject:
        """Persist a draft project version before running the LLM workflow."""

        version = self.store.next_version(request.enterprise_id)
        project = GenerationProject(
            id=request.project_id or f"ogp_{uuid4().hex}",
            enterprise_id=request.enterprise_id,
            product_ids=list(request.product_ids),
            selected_industry=request.selected_industry,
            target_countries=list(request.target_countries),
            generation_status=GenerationStatus.DRAFT,
            generated_by=request.generated_by,
            version=version,
            metadata={
                "extra_context": copy.deepcopy(request.extra_context),
                "execution_mode": "inline_sync",
                "plan_group_id": request.extra_context.get("plan_group_id") or request.project_id,
                "continue_on_validation_warning": request.continue_on_validation_warning,
            },
        )
        project.metadata["plan_group_id"] = project.metadata.get("plan_group_id") or project.id
        saved_project = self.store.save_project(project)
        self._write_project_audit_log(
            saved_project,
            action_type=OverseasPlanAuditAction.CREATE_PLAN,
            user_id=request.generated_by,
            username=request.username,
            result_status=AuditResultStatus.SUCCESS,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
        )
        return saved_project

    def run_generation(self, project_id: str, audit_context: RequestAuditContext | None = None) -> GenerationPreviewResponse:
        """Run the full enterprise/product/template/rule/DeepSeek workflow."""

        project = self.store.get_project(project_id)
        if project is None:
            raise DataNotFoundError(f"Generation project not found: {project_id}")

        project.generation_status = GenerationStatus.GENERATING
        project.metadata["started_at"] = utc_now().isoformat()
        self.store.save_project(project)

        success = False
        error_reason = None
        try:
            enterprise_data = self._load_enterprise_payload(project)
            readiness_report = assess_generation_readiness(enterprise_data)
            project.metadata["generation_readiness"] = readiness_report.to_dict()
            if readiness_report.should_popup and not project.metadata.get("continue_on_validation_warning"):
                raise GenerationValidationError(readiness_report.message)
            template_payload = self._load_templates(project, enterprise_data)
            rule_output = self.rule_engine.evaluate(enterprise_data) if self.rule_engine else {}
            prompt_bundle = build_overseas_plan_prompts(
                enterprise_data={**enterprise_data, "templates": template_payload, "generation_readiness": readiness_report.to_dict()},
                rule_engine_output=rule_output,
                resource_library=template_payload["resource_templates"],
                extra_context={"project_id": project.id, "version": project.version, "generation_readiness": readiness_report.to_dict(), **project.metadata.get("extra_context", {})},
            )
            raw_output = self.llm_client.generate_text(prompt_bundle.user_prompt, system_prompt=prompt_bundle.system_prompt)
            parsed_output = self._parse_validate_or_repair(raw_output, prompt_bundle, project, enterprise_data, rule_output)

            if project.metadata.get("continue_on_validation_warning") and readiness_report.manual_review_required:
                parsed_output.setdefault("data_quality_review", readiness_report.to_dict())
                parsed_output.setdefault("global_manual_review_items", [])
                if isinstance(parsed_output["global_manual_review_items"], list):
                    parsed_output["global_manual_review_items"].append("因生成前信息缺失，方案需人工补充/复核")
            project.result = parsed_output
            maturity = rule_output.get("maturity_assessment", {})
            project.final_score = maturity.get("total_score")
            if maturity.get("maturity_level"):
                project.maturity_level = MaturityLevel(maturity["maturity_level"])
            project.generation_status = GenerationStatus.COMPLETED
            project.error_reason = None
            project.metadata.update(
                {
                    "completed_at": utc_now().isoformat(),
                    "rule_engine_output": rule_output,
                    "prompt_model": getattr(getattr(self.llm_client, "config", None), "model", None),
                    "json_repaired": project.metadata.get("json_repaired", False),
                }
            )
            content_version = self._append_content_version(
                project,
                created_by=project.generated_by,
                generation_source=_source_from_extra_context(project.metadata.get("extra_context", {})),
                change_summary=project.metadata.get("extra_context", {}).get("reason") or "AI生成完成",
                content_json=parsed_output,
            )
            project.metadata["current_version_number"] = content_version.version_number
            success = True
        except Exception as exc:  # noqa: BLE001 - persist any orchestration failure for frontend visibility.
            error_reason = str(exc)
            project.generation_status = GenerationStatus.FAILED
            project.error_reason = error_reason
            project.metadata["failed_at"] = utc_now().isoformat()
            project.metadata["error_reason"] = error_reason
        finally:
            self.store.save_project(project)
            audit_log = self._write_project_audit_log(
                project,
                action_type=OverseasPlanAuditAction.AI_GENERATE_PLAN,
                user_id=(audit_context.user_id if audit_context else project.generated_by) or project.generated_by,
                username=audit_context.username if audit_context else None,
                result_status=AuditResultStatus.SUCCESS if success else AuditResultStatus.FAILED,
                error_message=error_reason,
                ip_address=audit_context.ip_address if audit_context else None,
                user_agent=audit_context.user_agent if audit_context else None,
            )

        return GenerationPreviewResponse(project=project.to_dict(), preview=project.result, audit_log=audit_log.to_dict())


    def view_plan_detail(
        self,
        project_id: str,
        *,
        user_id: str,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Return plan detail and audit the view action."""

        project = self.store.get_project(project_id)
        if project is None:
            self._write_audit_log(
                action_type=OverseasPlanAuditAction.VIEW_PLAN_DETAIL,
                user_id=user_id,
                username=username,
                enterprise_id=None,
                plan_id=project_id,
                product_ids=[],
                target_countries=[],
                result_status=AuditResultStatus.FAILED,
                error_message=f"Generation project not found: {project_id}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise DataNotFoundError(f"Generation project not found: {project_id}")
        self._write_project_audit_log(
            project,
            action_type=OverseasPlanAuditAction.VIEW_PLAN_DETAIL,
            user_id=user_id,
            username=username,
            result_status=AuditResultStatus.SUCCESS,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return project.to_dict()

    def update_generated_content(
        self,
        project_id: str,
        *,
        result: dict[str, Any],
        edited_by: str,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationProject:
        """Replace AI generated content and audit only changed top-level fields."""

        project = self.store.get_project(project_id)
        if project is None:
            self._write_audit_log(
                action_type=OverseasPlanAuditAction.EDIT_AI_CONTENT,
                user_id=edited_by,
                username=username,
                enterprise_id=None,
                plan_id=project_id,
                product_ids=[],
                target_countries=[],
                result_status=AuditResultStatus.FAILED,
                error_message=f"Generation project not found: {project_id}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise DataNotFoundError(f"Generation project not found: {project_id}")
        previous_keys = set(project.result or {}) if isinstance(project.result, dict) else set()
        new_keys = set(result)
        project.result = copy.deepcopy(result)
        project.generation_status = GenerationStatus.COMPLETED
        project.metadata["last_edited_at"] = utc_now().isoformat()
        project.metadata["last_edited_by"] = edited_by
        version = self._append_content_version(
            project,
            created_by=edited_by,
            generation_source=GenerationSource.USER_EDIT,
            change_summary=f"用户编辑：{', '.join(sorted(previous_keys ^ new_keys)) or '正文内容调整'}",
            content_json=result,
        )
        project.metadata["current_version_number"] = version.version_number
        saved = self.store.save_project(project)
        self._write_project_audit_log(
            saved,
            action_type=OverseasPlanAuditAction.EDIT_AI_CONTENT,
            user_id=edited_by,
            username=username,
            result_status=AuditResultStatus.SUCCESS,
            metadata={"changed_top_level_fields": sorted(previous_keys ^ new_keys), "version_number": version.version_number},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return saved

    def list_versions(self, project_id: str) -> PlanVersionListResponse:
        """List immutable content versions in the same plan history group."""

        project = self.store.get_project(project_id)
        if project is None:
            raise DataNotFoundError(f"Generation project not found: {project_id}")
        versions = self.store.list_content_versions(project_id)
        final_version = next((version for version in versions if version.is_final), None)
        return PlanVersionListResponse(
            project_id=project_id,
            current_version_number=project.metadata.get("current_version_number"),
            final_version_number=final_version.version_number if final_version else None,
            versions=[version.to_dict() for version in versions],
        )

    def get_version(self, project_id: str, version_number: int) -> dict[str, Any]:
        """Return one historical content version for preview switching."""

        version = self.store.get_content_version(project_id, version_number)
        if version is None:
            raise DataNotFoundError(f"Plan version not found: {project_id} v{version_number}")
        return version.to_dict()

    def restore_version(
        self,
        project_id: str,
        version_number: int,
        *,
        restored_by: str,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationProject:
        """Restore a historical version as the current editable version without deleting history."""

        project = self.store.get_project(project_id)
        version = self.store.get_content_version(project_id, version_number)
        if project is None or version is None:
            raise DataNotFoundError(f"Plan version not found: {project_id} v{version_number}")
        project.result = copy.deepcopy(version.content_json)
        project.generation_status = GenerationStatus.COMPLETED
        restored_version = self._append_content_version(
            project,
            created_by=restored_by,
            generation_source=GenerationSource.USER_EDIT,
            change_summary=f"恢复自历史版本 v{version_number}",
            content_json=version.content_json,
        )
        project.metadata["current_version_number"] = restored_version.version_number
        saved = self.store.save_project(project)
        self._write_project_audit_log(
            saved,
            action_type=OverseasPlanAuditAction.RESTORE_VERSION,
            user_id=restored_by,
            username=username,
            result_status=AuditResultStatus.SUCCESS,
            metadata={"restored_from_version": version_number, "version_number": restored_version.version_number},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return saved

    def mark_final_version(
        self,
        project_id: str,
        version_number: int,
        *,
        finalized_by: str,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Mark one version as final; only one final version exists per plan history group."""

        project = self.store.get_project(project_id)
        version = self.store.mark_final_content_version(project_id, version_number, finalized_by=finalized_by)
        if project is None or version is None:
            raise DataNotFoundError(f"Plan version not found: {project_id} v{version_number}")
        project.metadata["final_version_number"] = version_number
        self.store.save_project(project)
        self._write_project_audit_log(
            project,
            action_type=OverseasPlanAuditAction.MARK_FINAL_VERSION,
            user_id=finalized_by,
            username=username,
            result_status=AuditResultStatus.SUCCESS,
            metadata={"final_version_number": version_number},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return version.to_dict()

    def archive_plan(
        self,
        project_id: str,
        *,
        user_id: str,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationProject:
        """Mark a plan as archived and audit the archive action."""

        project = self.store.get_project(project_id)
        if project is None:
            self._write_audit_log(
                action_type=OverseasPlanAuditAction.ARCHIVE_PLAN,
                user_id=user_id,
                username=username,
                enterprise_id=None,
                plan_id=project_id,
                product_ids=[],
                target_countries=[],
                result_status=AuditResultStatus.FAILED,
                error_message=f"Generation project not found: {project_id}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise DataNotFoundError(f"Generation project not found: {project_id}")
        project.metadata["archived"] = True
        project.metadata["archived_at"] = utc_now().isoformat()
        project.metadata["archived_by"] = user_id
        saved = self.store.save_project(project)
        self._write_project_audit_log(
            saved,
            action_type=OverseasPlanAuditAction.ARCHIVE_PLAN,
            user_id=user_id,
            username=username,
            result_status=AuditResultStatus.SUCCESS,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return saved

    def delete_plan(
        self,
        project_id: str,
        *,
        user_id: str,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationProject:
        """Delete a plan from the lightweight store and keep the audit trail."""

        project = self.store.delete_project(project_id)
        if project is None:
            self._write_audit_log(
                action_type=OverseasPlanAuditAction.DELETE_PLAN,
                user_id=user_id,
                username=username,
                enterprise_id=None,
                plan_id=project_id,
                product_ids=[],
                target_countries=[],
                result_status=AuditResultStatus.FAILED,
                error_message=f"Generation project not found: {project_id}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise DataNotFoundError(f"Generation project not found: {project_id}")
        self._write_project_audit_log(
            project,
            action_type=OverseasPlanAuditAction.DELETE_PLAN,
            user_id=user_id,
            username=username,
            result_status=AuditResultStatus.SUCCESS,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return project

    def list_plan_audit_logs(self, query: AuditLogQuery | None = None) -> list[dict[str, Any]]:
        """Query audit logs by enterprise, user, action type and time range."""

        return [log.to_dict() for log in self.store.list_audit_logs(query=query)]

    def export_word(self, request: WordExportRequest) -> WordExportResult:
        """Export a completed overseas-plan project to a Word document."""

        project = self.store.get_project(request.project_id)
        try:
            if project is None:
                raise DataNotFoundError(f"Generation project not found: {request.project_id}")
            export_project = self._project_for_export(project)
            if export_project.result is None:
                raise GenerationServiceError(f"Generation project has no exportable result: {request.project_id}")
            enterprise = self.data_repository.get_enterprise(export_project.enterprise_id)
            result = export_overseas_plan_word(
                project=export_project.to_dict(),
                enterprise=enterprise,
                output_dir=request.output_dir,
                exported_by=request.exported_by,
                system_name=request.system_name,
            )
            project.output_word = GeneratedFileRef(file_path=result.file_path)
            self.store.save_project(project)
            self._write_export_audit_log(project=project, enterprise=enterprise, export_result=result, request=request)
            return result
        except Exception as exc:
            self._write_export_failure_audit_log(
                action_type=OverseasPlanAuditAction.EXPORT_WORD,
                export_type="Word",
                project=project,
                request=request,
                error_message=str(exc),
            )
            raise

    def export_excel(self, request: ExcelExportRequest) -> ExcelExportResult:
        """Export a completed overseas-plan project to an Excel workbook."""

        project = self.store.get_project(request.project_id)
        try:
            if project is None:
                raise DataNotFoundError(f"Generation project not found: {request.project_id}")
            export_project = self._project_for_export(project)
            if export_project.result is None:
                raise GenerationServiceError(f"Generation project has no exportable result: {request.project_id}")
            enterprise = self.data_repository.get_enterprise(export_project.enterprise_id)
            result = export_overseas_plan_excel(
                project=export_project.to_dict(),
                enterprise=enterprise,
                export_kind=request.export_kind,
                output_dir=request.output_dir,
                exported_by=request.exported_by,
                system_name=request.system_name,
            )
            project.output_excel = GeneratedFileRef(file_path=result.file_path)
            self.store.save_project(project)
            self._write_export_audit_log(project=project, enterprise=enterprise, export_result=result, request=request)
            return result
        except Exception as exc:
            self._write_export_failure_audit_log(
                action_type=_excel_export_action_type(getattr(request, "export_kind", None)),
                export_type="Excel",
                project=project,
                request=request,
                error_message=str(exc),
            )
            raise

    def export_ppt(self, request: PPTExportRequest) -> PPTExportResult:
        """Export a completed overseas-plan project to a PowerPoint deck."""

        project = self.store.get_project(request.project_id)
        try:
            if project is None:
                raise DataNotFoundError(f"Generation project not found: {request.project_id}")
            export_project = self._project_for_export(project)
            if export_project.result is None:
                raise GenerationServiceError(f"Generation project has no exportable result: {request.project_id}")
            enterprise = self.data_repository.get_enterprise(export_project.enterprise_id)
            result = export_overseas_plan_ppt(
                project=export_project.to_dict(),
                enterprise=enterprise,
                output_dir=request.output_dir,
                exported_by=request.exported_by,
                system_name=request.system_name,
            )
            project.output_ppt = GeneratedFileRef(file_path=result.file_path)
            self.store.save_project(project)
            self._write_export_audit_log(project=project, enterprise=enterprise, export_result=result, request=request)
            return result
        except Exception as exc:
            self._write_export_failure_audit_log(
                action_type=OverseasPlanAuditAction.EXPORT_PPT,
                export_type="PPT",
                project=project,
                request=request,
                error_message=str(exc),
            )
            raise

    def _append_content_version(
        self,
        project: GenerationProject,
        *,
        created_by: str | None,
        generation_source: GenerationSource,
        change_summary: str | None,
        content_json: dict[str, Any],
    ) -> PlanContentVersion:
        return self.store.append_content_version(
            PlanContentVersion(
                project_id=project.id,
                source_project_id=project.id,
                version_number=self.store.next_content_version(project.id),
                created_by=created_by,
                created_at=utc_now(),
                generation_source=generation_source,
                change_summary=change_summary,
                content_json=copy.deepcopy(content_json),
                generation_status=GenerationStatus.COMPLETED,
            )
        )

    def _project_for_export(self, project: GenerationProject) -> GenerationProject:
        selected_version = self.store.find_export_content_version(project.id)
        if selected_version is None:
            return project
        export_project = copy.deepcopy(project)
        export_project.result = copy.deepcopy(selected_version.content_json)
        export_project.version = selected_version.version_number
        export_project.metadata["export_version_number"] = selected_version.version_number
        export_project.metadata["export_version_source"] = selected_version.generation_source.value
        export_project.metadata["export_uses_final_version"] = selected_version.is_final
        return export_project

    def _load_enterprise_payload(self, project: GenerationProject) -> dict[str, Any]:
        enterprise = self.data_repository.get_enterprise(project.enterprise_id)
        products = self.data_repository.get_products(project.enterprise_id, project.product_ids)
        payload = {
            "enterprise": {**enterprise, "industry": project.selected_industry or enterprise.get("industry")},
            "products": products,
            "target_markets": list(project.target_countries),
        }
        payload.update(_derive_product_fields(products))
        payload.update({key: value for key, value in enterprise.items() if key not in payload["enterprise"]})
        return payload

    def _load_templates(self, project: GenerationProject, enterprise_data: dict[str, Any]) -> dict[str, Any]:
        country_templates = [self.template_repository.get_country(country) for country in project.target_countries]
        regions = {country.region for country in country_templates if country is not None}
        industry_templates = self.template_repository.match_industries(country_name=project.target_countries[0]) if project.target_countries else []
        selected_industry = self.template_repository.get_industry(project.selected_industry)
        if selected_industry:
            industry_templates = [selected_industry, *[item for item in industry_templates if item.industry_name != selected_industry.industry_name]]
        resource_templates = []
        for region in regions or {None}:
            resource_templates.extend(self.template_repository.match_resources(industry_name=enterprise_data["enterprise"].get("industry"), region=region))
        return {
            "industry_templates": [_dataclass_to_dict(item) for item in industry_templates],
            "country_templates": [_dataclass_to_dict(item) for item in country_templates if item is not None],
            "resource_templates": [_dataclass_to_dict(item) for item in _dedupe_template_objects(resource_templates, "resource_type")],
        }

    def _parse_validate_or_repair(
        self,
        raw_output: str,
        prompt_bundle: Any,
        project: GenerationProject,
        enterprise_data: dict[str, Any],
        rule_output: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            parsed = self._parse_and_validate_json(raw_output)
            project.metadata["json_repaired"] = False
            return parsed
        except GenerationValidationError as first_exc:
            repair_prompt = _build_repair_prompt(raw_output, str(first_exc), prompt_bundle.json_structure_example)
            try:
                repaired_output = self.llm_client.generate_text(repair_prompt, system_prompt=prompt_bundle.system_prompt)
                parsed = self._parse_and_validate_json(repaired_output)
                project.metadata["json_repaired"] = True
                project.metadata["json_repair_reason"] = str(first_exc)
                return parsed
            except (GenerationValidationError, LLMServiceError) as second_exc:
                raise GenerationValidationError(f"DeepSeek JSON validation failed after one repair retry: {second_exc}") from second_exc

    def _parse_and_validate_json(self, raw_output: str) -> dict[str, Any]:
        try:
            parsed = json.loads(_strip_markdown_fence(raw_output))
        except json.JSONDecodeError as exc:
            raise GenerationValidationError("DeepSeek returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise GenerationValidationError("DeepSeek JSON root must be an object")
        _validate_plan_payload(parsed)
        return parsed

    def _write_project_audit_log(
        self,
        project: GenerationProject,
        *,
        action_type: str,
        user_id: str | None,
        username: str | None,
        result_status: str,
        error_message: str | None = None,
        export_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> OverseasPlanAuditLog:
        return self._write_audit_log(
            action_type=action_type,
            user_id=user_id,
            username=username,
            enterprise_id=project.enterprise_id,
            plan_id=project.id,
            product_ids=list(project.product_ids),
            target_countries=list(project.target_countries),
            result_status=result_status,
            error_message=error_message,
            export_type=export_type,
            ip_address=ip_address,
            user_agent=user_agent,
            version=project.version,
            generated_by=project.generated_by,
            metadata=metadata,
        )

    def _write_audit_log(
        self,
        *,
        action_type: str,
        user_id: str | None,
        username: str | None,
        enterprise_id: str | None,
        plan_id: str | None,
        product_ids: list[str],
        target_countries: list[str],
        result_status: str,
        error_message: str | None = None,
        export_type: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        version: int | None = None,
        generated_by: str | None = None,
        generated_at: str | None = None,
        exported_by: str | None = None,
        exported_at: str | None = None,
        enterprise_name: str | None = None,
        plan_name: str | None = None,
        file_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OverseasPlanAuditLog:
        created_at = utc_now().isoformat()
        success = result_status == AuditResultStatus.SUCCESS
        audit_log = OverseasPlanAuditLog(
            id=f"opa_{uuid4().hex}",
            user_id=user_id,
            username=username,
            action_type=action_type,
            enterprise_id=enterprise_id,
            plan_id=plan_id,
            product_ids=list(product_ids),
            target_countries=list(target_countries),
            export_type=export_type,
            created_at=created_at,
            ip_address=ip_address,
            user_agent=user_agent,
            result_status=result_status,
            error_message=error_message,
            metadata=copy.deepcopy(metadata or {}),
            project_id=plan_id,
            version=version,
            generated_by=generated_by or user_id,
            generated_at=generated_at or (created_at if action_type == OverseasPlanAuditAction.AI_GENERATE_PLAN else None),
            success=success,
            error_reason=error_message,
            exported_by=exported_by,
            exported_at=exported_at,
            enterprise_name=enterprise_name,
            plan_name=plan_name,
            file_path=file_path,
        )
        return self.store.append_audit_log(audit_log)

    def _write_export_audit_log(
        self,
        *,
        project: GenerationProject,
        enterprise: dict[str, Any],
        export_result: WordExportResult | PPTExportResult | ExcelExportResult,
        request: WordExportRequest | PPTExportRequest | ExcelExportRequest,
    ) -> ExportAuditLog:
        action_type = _export_action_type(export_result)
        return self._write_audit_log(
            action_type=action_type,
            user_id=export_result.exported_by,
            username=getattr(request, "username", None),
            enterprise_id=project.enterprise_id,
            enterprise_name=enterprise.get("name") or enterprise.get("enterprise_name") or project.enterprise_id,
            plan_id=project.id,
            product_ids=list(project.product_ids),
            target_countries=list(project.target_countries),
            export_type=export_result.export_type,
            result_status=AuditResultStatus.SUCCESS,
            ip_address=getattr(request, "ip_address", None),
            user_agent=getattr(request, "user_agent", None),
            version=project.version,
            exported_by=export_result.exported_by,
            exported_at=export_result.exported_at,
            plan_name=export_result.plan_name,
            file_path=export_result.file_path,
            metadata={"export_kind": getattr(export_result, "export_kind", None)},
        )

    def _write_export_failure_audit_log(
        self,
        *,
        action_type: str,
        export_type: str,
        project: GenerationProject | None,
        request: WordExportRequest | PPTExportRequest | ExcelExportRequest,
        error_message: str,
    ) -> OverseasPlanAuditLog:
        return self._write_audit_log(
            action_type=action_type,
            user_id=getattr(request, "exported_by", None),
            username=getattr(request, "username", None),
            enterprise_id=project.enterprise_id if project else None,
            plan_id=getattr(request, "project_id", None),
            product_ids=list(project.product_ids) if project else [],
            target_countries=list(project.target_countries) if project else [],
            export_type=export_type,
            result_status=AuditResultStatus.FAILED,
            error_message=error_message,
            ip_address=getattr(request, "ip_address", None),
            user_agent=getattr(request, "user_agent", None),
            version=project.version if project else None,
            exported_by=getattr(request, "exported_by", None),
        )


def _source_from_extra_context(extra_context: dict[str, Any]) -> GenerationSource:
    if extra_context.get("generation_source") == GenerationSource.REGENERATED.value or extra_context.get("regenerated_from_project_id"):
        return GenerationSource.REGENERATED
    return GenerationSource.AI_GENERATED


def _context_from_generation_request(request: GenerationRequest) -> RequestAuditContext:
    return RequestAuditContext(
        user_id=request.generated_by,
        username=request.username,
        ip_address=request.ip_address,
        user_agent=request.user_agent,
    )


def _is_export_action(action_type: str) -> bool:
    return action_type in {
        OverseasPlanAuditAction.EXPORT_WORD,
        OverseasPlanAuditAction.EXPORT_PPT,
        OverseasPlanAuditAction.EXPORT_EXCEL_ACTION_PLAN,
        OverseasPlanAuditAction.EXPORT_RESOURCE_LIST,
    }


def _excel_export_action_type(export_kind: Any) -> str:
    value = getattr(export_kind, "value", export_kind)
    if value == "resource_list":
        return OverseasPlanAuditAction.EXPORT_RESOURCE_LIST
    return OverseasPlanAuditAction.EXPORT_EXCEL_ACTION_PLAN


def _export_action_type(export_result: WordExportResult | PPTExportResult | ExcelExportResult) -> str:
    if isinstance(export_result, ExcelExportResult):
        return _excel_export_action_type(export_result.export_kind)
    if export_result.export_type == "PPT":
        return OverseasPlanAuditAction.EXPORT_PPT
    return OverseasPlanAuditAction.EXPORT_WORD


def _filter_audit_logs(logs: list[OverseasPlanAuditLog], query: AuditLogQuery) -> list[OverseasPlanAuditLog]:
    filtered = logs
    if query.enterprise_id is not None:
        filtered = [log for log in filtered if log.enterprise_id == query.enterprise_id]
    if query.user_id is not None:
        filtered = [log for log in filtered if log.user_id == query.user_id]
    if query.username is not None:
        filtered = [log for log in filtered if log.username == query.username]
    if query.action_type is not None:
        filtered = [log for log in filtered if log.action_type == query.action_type]
    if query.plan_id is not None:
        filtered = [log for log in filtered if log.plan_id == query.plan_id or log.project_id == query.plan_id]
    if query.created_from is not None:
        start = _parse_audit_datetime(query.created_from)
        filtered = [log for log in filtered if _parse_audit_datetime(log.created_at) >= start]
    if query.created_to is not None:
        end = _parse_audit_datetime(query.created_to)
        filtered = [log for log in filtered if _parse_audit_datetime(log.created_at) <= end]
    return filtered


def _parse_audit_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _derive_product_fields(products: list[dict[str, Any]]) -> dict[str, Any]:
    certifications = []
    hs_codes = []
    price_bands = []
    monthly_units = 0.0
    moqs = []
    for product in products:
        certifications.extend(product.get("certifications", []) or [])
        if product.get("hs_code"):
            hs_codes.append(product["hs_code"])
        if product.get("price_band"):
            price_bands.append(product["price_band"])
        monthly_units += float(product.get("capacity", {}).get("monthly_units", product.get("monthly_capacity", 0)) or 0)
        if product.get("moq"):
            moqs.append(product["moq"])
    return {
        "certifications": _dedupe_strings(certifications),
        "hs_codes": _dedupe_strings(hs_codes),
        "price_band": "; ".join(_dedupe_strings(price_bands)),
        "capacity": {"monthly_units": monthly_units},
        "moq": "; ".join(map(str, moqs)),
    }


def _validate_plan_payload(payload: dict[str, Any]) -> None:
    sections = payload.get("sections")
    if not isinstance(sections, dict):
        raise GenerationValidationError("DeepSeek JSON must contain object field: sections")
    required_sections = {
        "01_enterprise_diagnosis",
        "02_overseas_market_selection",
        "03_entry_mode_design",
        "04_overseas_resource_matching_plan",
        "05_exhibition_and_marketing_plan",
        "06_financing_and_capacity_expansion_plan",
        "07_12_24_month_implementation_roadmap",
    }
    missing = sorted(required_sections - set(sections))
    if missing:
        raise GenerationValidationError(f"DeepSeek JSON missing required sections: {', '.join(missing)}")


def _build_repair_prompt(raw_output: str, error_reason: str, structure_example: dict[str, Any]) -> str:
    return (
        "上一次 DeepSeek 输出未通过 JSON 校验，请只返回修复后的合法 JSON 对象，不要输出 Markdown 或解释。\n"
        f"校验失败原因：{error_reason}\n"
        f"必须遵循的结构示例：{json.dumps(structure_example, ensure_ascii=False)}\n"
        f"待修复内容：\n{raw_output}"
    )


def _strip_markdown_fence(value: str) -> str:
    stripped = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def _dataclass_to_dict(item: Any) -> dict[str, Any]:
    return asdict(item)


def _dedupe_template_objects(items: list[Any], attribute_name: str) -> list[Any]:
    seen = set()
    result = []
    for item in items:
        key = getattr(item, attribute_name)
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result


def _dedupe_strings(items: list[Any]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = str(item)
        if key and key not in seen:
            result.append(key)
            seen.add(key)
    return result
