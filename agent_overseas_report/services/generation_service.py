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
from typing import Any, Protocol
from uuid import uuid4

from agent_overseas_report.knowledge_base.repository import KnowledgeBaseTemplateRepository, get_default_template_repository
from agent_overseas_report.models import GeneratedFileRef, GenerationProject, GenerationStatus, MaturityLevel
from agent_overseas_report.models.overseas_generation import utc_now
from agent_overseas_report.prompts import build_overseas_plan_prompts
from agent_overseas_report.services.llm_service import LLMServiceError
from agent_overseas_report.services.rule_engine import OverseasRuleEngine
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
class GenerationRequest:
    """Input DTO for creating a new overseas-plan generation version."""

    enterprise_id: str
    product_ids: list[str]
    selected_industry: str
    target_countries: list[str]
    generated_by: str
    project_id: str | None = None
    extra_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GenerationAuditLog:
    """Append-only audit record for every generation attempt."""

    id: str
    project_id: str
    version: int
    generated_by: str
    generated_at: str
    enterprise_id: str
    product_ids: list[str]
    target_countries: list[str]
    success: bool
    error_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable audit-log payload."""

        return asdict(self)


@dataclass(slots=True)
class ExportAuditLog:
    """Append-only audit record for every document export action."""

    id: str
    project_id: str
    version: int
    exported_by: str
    exported_at: str
    enterprise_id: str
    enterprise_name: str
    plan_name: str
    export_type: str
    file_path: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable export audit-log payload."""

        return asdict(self)


@dataclass(slots=True)
class GenerationPreviewResponse:
    """Frontend preview payload returned after a generation run."""

    project: dict[str, Any]
    preview: dict[str, Any] | None
    audit_log: dict[str, Any]


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
    save project, find latest version, and append audit logs.
    """

    def __init__(self) -> None:
        self._projects: dict[str, GenerationProject] = {}
        self._audit_logs: list[GenerationAuditLog] = []
        self._export_audit_logs: list[ExportAuditLog] = []

    def next_version(self, enterprise_id: str) -> int:
        versions = [project.version for project in self._projects.values() if project.enterprise_id == enterprise_id]
        return max(versions, default=0) + 1

    def save_project(self, project: GenerationProject) -> GenerationProject:
        project.updated_at = utc_now()
        self._projects[project.id] = copy.deepcopy(project)
        return project

    def get_project(self, project_id: str) -> GenerationProject | None:
        project = self._projects.get(project_id)
        return copy.deepcopy(project) if project else None

    def append_audit_log(self, audit_log: GenerationAuditLog) -> GenerationAuditLog:
        self._audit_logs.append(copy.deepcopy(audit_log))
        return audit_log

    def list_audit_logs(self, project_id: str | None = None) -> list[GenerationAuditLog]:
        logs = self._audit_logs
        if project_id is not None:
            logs = [log for log in logs if log.project_id == project_id]
        return copy.deepcopy(logs)

    def append_export_audit_log(self, audit_log: ExportAuditLog) -> ExportAuditLog:
        self._export_audit_logs.append(copy.deepcopy(audit_log))
        return audit_log

    def list_export_audit_logs(self, project_id: str | None = None) -> list[ExportAuditLog]:
        logs = self._export_audit_logs
        if project_id is not None:
            logs = [log for log in logs if log.project_id == project_id]
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
        return self.run_generation(project.id)

    def regenerate(self, project_id: str, *, generated_by: str, extra_context: dict[str, Any] | None = None) -> GenerationPreviewResponse:
        """Generate a new version from a historical project without overwriting it."""

        previous = self.store.get_project(project_id)
        if previous is None:
            raise DataNotFoundError(f"Generation project not found: {project_id}")
        request = GenerationRequest(
            enterprise_id=previous.enterprise_id,
            product_ids=previous.product_ids,
            selected_industry=previous.selected_industry,
            target_countries=previous.target_countries,
            generated_by=generated_by,
            extra_context={"regenerated_from_project_id": project_id, **(extra_context or {})},
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
            metadata={"extra_context": copy.deepcopy(request.extra_context), "execution_mode": "inline_sync"},
        )
        return self.store.save_project(project)

    def run_generation(self, project_id: str) -> GenerationPreviewResponse:
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
            template_payload = self._load_templates(project, enterprise_data)
            rule_output = self.rule_engine.evaluate(enterprise_data) if self.rule_engine else {}
            prompt_bundle = build_overseas_plan_prompts(
                enterprise_data={**enterprise_data, "templates": template_payload},
                rule_engine_output=rule_output,
                resource_library=template_payload["resource_templates"],
                extra_context={"project_id": project.id, "version": project.version, **project.metadata.get("extra_context", {})},
            )
            raw_output = self.llm_client.generate_text(prompt_bundle.user_prompt, system_prompt=prompt_bundle.system_prompt)
            parsed_output = self._parse_validate_or_repair(raw_output, prompt_bundle, project, enterprise_data, rule_output)

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
            success = True
        except Exception as exc:  # noqa: BLE001 - persist any orchestration failure for frontend visibility.
            error_reason = str(exc)
            project.generation_status = GenerationStatus.FAILED
            project.error_reason = error_reason
            project.metadata["failed_at"] = utc_now().isoformat()
            project.metadata["error_reason"] = error_reason
        finally:
            self.store.save_project(project)
            audit_log = self._write_audit_log(project, success=success, error_reason=error_reason)

        return GenerationPreviewResponse(project=project.to_dict(), preview=project.result, audit_log=audit_log.to_dict())


    def export_word(self, request: WordExportRequest) -> WordExportResult:
        """Export a completed overseas-plan project to a Word document.

        The method keeps the existing Excel export slot untouched and only updates
        ``output_word`` plus the dedicated export audit log. API handlers can map
        this method to ``POST /api/overseas-plans/{project_id}/exports/word``.
        """

        project = self.store.get_project(request.project_id)
        if project is None:
            raise DataNotFoundError(f"Generation project not found: {request.project_id}")
        if project.result is None:
            raise GenerationServiceError(f"Generation project has no exportable result: {request.project_id}")

        enterprise = self.data_repository.get_enterprise(project.enterprise_id)
        result = export_overseas_plan_word(
            project=project.to_dict(),
            enterprise=enterprise,
            output_dir=request.output_dir,
            exported_by=request.exported_by,
            system_name=request.system_name,
        )

        project.output_word = GeneratedFileRef(file_path=result.file_path)
        self.store.save_project(project)
        self._write_export_audit_log(project=project, enterprise=enterprise, export_result=result)
        return result

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

    def _write_audit_log(self, project: GenerationProject, *, success: bool, error_reason: str | None) -> GenerationAuditLog:
        audit_log = GenerationAuditLog(
            id=f"oga_{uuid4().hex}",
            project_id=project.id,
            version=project.version,
            generated_by=project.generated_by or "system",
            generated_at=utc_now().isoformat(),
            enterprise_id=project.enterprise_id,
            product_ids=list(project.product_ids),
            target_countries=list(project.target_countries),
            success=success,
            error_reason=error_reason,
        )
        return self.store.append_audit_log(audit_log)

    def _write_export_audit_log(self, *, project: GenerationProject, enterprise: dict[str, Any], export_result: WordExportResult) -> ExportAuditLog:
        audit_log = ExportAuditLog(
            id=f"oea_{uuid4().hex}",
            project_id=project.id,
            version=project.version,
            exported_by=export_result.exported_by,
            exported_at=export_result.exported_at,
            enterprise_id=project.enterprise_id,
            enterprise_name=enterprise.get("name") or enterprise.get("enterprise_name") or project.enterprise_id,
            plan_name=export_result.plan_name,
            export_type="Word",
            file_path=export_result.file_path,
        )
        return self.store.append_export_audit_log(audit_log)


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
