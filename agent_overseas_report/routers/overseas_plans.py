"""Overseas-plan API routes backed by ``OverseasPlanGenerationService``."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agent_overseas_report.schemas import (
    EditOverseasPlanRequest,
    EditOverseasPlanResponse,
    ErrorResponse,
    ExportOverseasPlanRequest,
    ExportOverseasPlanResponse,
    FinalizeOverseasPlanRequest,
    FinalizeOverseasPlanResponse,
    GenerateOverseasPlanRequest,
    OverseasPlanDetailResponse,
    OverseasPlanAuditLogListResponse,
    OverseasPlanGenerationResponse,
    OverseasPlanVersionListResponse,
    OverseasPlanVersionResponse,
    RegenerateOverseasPlanRequest,
    RestoreOverseasPlanVersionRequest,
    RestoreOverseasPlanVersionResponse,
)
from agent_overseas_report.services import (
    DataNotFoundError,
    ExcelExportKind,
    ExcelExportRequest,
    GenerationRequest,
    GenerationServiceError,
    OverseasPlanGenerationService,
    PPTExportRequest,
    WordExportRequest,
)
from agent_overseas_report.dependencies import get_generation_service

router = APIRouter(prefix="/overseas-plans", tags=["overseas-plans"])


def _client_ip(request: Request) -> str | None:
    """Extract the best-effort client IP from a request."""

    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    """Extract user-agent text for audit metadata."""

    return request.headers.get("user-agent")


def _raise_http_error(exc: Exception) -> None:
    """Map service exceptions to HTTP errors."""

    if isinstance(exc, DataNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, GenerationServiceError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post(
    "/generate",
    response_model=OverseasPlanGenerationResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Generate an overseas plan",
)
def generate_overseas_plan(
    payload: GenerateOverseasPlanRequest,
    request: Request,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> OverseasPlanGenerationResponse:
    """Synchronously create and generate a plan via the existing service."""

    generation_request = GenerationRequest(
        enterprise_id=payload.enterprise_id,
        product_ids=payload.product_ids,
        selected_industry=payload.selected_industry,
        target_countries=payload.target_countries,
        generated_by=payload.generated_by,
        project_id=payload.project_id,
        extra_context=payload.extra_context,
        continue_on_validation_warning=payload.continue_on_validation_warning,
        username=payload.username,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    try:
        result = service.generate(generation_request)
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return OverseasPlanGenerationResponse(project=result.project, preview=result.preview, audit_log=result.audit_log)


@router.get(
    "/{project_id}",
    response_model=OverseasPlanDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get overseas plan detail",
)
def get_overseas_plan(
    project_id: str,
    request: Request,
    viewed_by: str = "api-user",
    username: str | None = None,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> OverseasPlanDetailResponse:
    """Return a generated plan project and write a view audit record."""

    try:
        project = service.view_plan_detail(
            project_id,
            user_id=viewed_by,
            username=username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return OverseasPlanDetailResponse(project=project)


@router.get(
    "/{project_id}/versions",
    response_model=OverseasPlanVersionListResponse,
    responses={404: {"model": ErrorResponse}},
    summary="List overseas plan versions",
)
def list_overseas_plan_versions(
    project_id: str,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> OverseasPlanVersionListResponse:
    """List immutable content versions for a plan history group."""

    try:
        versions = service.list_versions(project_id)
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return OverseasPlanVersionListResponse(
        project_id=versions.project_id,
        current_version_number=versions.current_version_number,
        final_version_number=versions.final_version_number,
        versions=versions.versions,
    )


@router.post(
    "/{project_id}/regenerate",
    response_model=OverseasPlanGenerationResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Regenerate an overseas plan",
)
def regenerate_overseas_plan(
    project_id: str,
    payload: RegenerateOverseasPlanRequest,
    request: Request,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> OverseasPlanGenerationResponse:
    """Create a new generated project version from an existing project."""

    try:
        result = service.regenerate(
            project_id,
            generated_by=payload.generated_by,
            extra_context=payload.extra_context,
            username=payload.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return OverseasPlanGenerationResponse(project=result.project, preview=result.preview, audit_log=result.audit_log)


@router.post(
    "/{project_id}/finalize",
    response_model=FinalizeOverseasPlanResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Finalize an overseas plan version",
)
def finalize_overseas_plan(
    project_id: str,
    payload: FinalizeOverseasPlanRequest,
    request: Request,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> FinalizeOverseasPlanResponse:
    """Mark one content version as the final version for the plan history group."""

    try:
        version = service.mark_final_version(
            project_id,
            payload.version_number,
            finalized_by=payload.finalized_by,
            username=payload.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return FinalizeOverseasPlanResponse(version=version)


@router.get(
    "/{project_id}/versions/{version_number}",
    response_model=OverseasPlanVersionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get one overseas plan version",
)
def get_overseas_plan_version(
    project_id: str,
    version_number: int,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> OverseasPlanVersionResponse:
    """Return a single immutable historical version for preview or restore review."""

    try:
        version = service.get_version(project_id, version_number)
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return OverseasPlanVersionResponse(version=version)


@router.post(
    "/{project_id}/edit",
    response_model=EditOverseasPlanResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Save a manual edit as a new version",
)
def edit_overseas_plan(
    project_id: str,
    payload: EditOverseasPlanRequest,
    request: Request,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> EditOverseasPlanResponse:
    """Persist edited report JSON as a new content version without overwriting history."""

    try:
        project = service.update_generated_content(
            project_id,
            result=payload.result,
            edited_by=payload.edited_by,
            username=payload.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return EditOverseasPlanResponse(project=project.to_dict())


@router.post(
    "/{project_id}/versions/{version_number}/restore",
    response_model=RestoreOverseasPlanVersionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Restore a historical version",
)
def restore_overseas_plan_version(
    project_id: str,
    version_number: int,
    payload: RestoreOverseasPlanVersionRequest,
    request: Request,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> RestoreOverseasPlanVersionResponse:
    """Restore a historical version by creating a new current version."""

    try:
        project = service.restore_version(
            project_id,
            version_number,
            restored_by=payload.restored_by,
            username=payload.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return RestoreOverseasPlanVersionResponse(project=project.to_dict())


@router.get(
    "/{project_id}/audit-logs",
    response_model=OverseasPlanAuditLogListResponse,
    responses={404: {"model": ErrorResponse}},
    summary="List overseas plan audit logs",
)
def list_overseas_plan_audit_logs(
    project_id: str,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> OverseasPlanAuditLogListResponse:
    """List append-only audit records for generation, editing, finalization and exports."""

    if service.store.get_project(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Generation project not found: {project_id}")
    logs = [log.to_dict() for log in service.store.list_audit_logs(project_id)]
    return OverseasPlanAuditLogListResponse(project_id=project_id, logs=logs)


@router.post(
    "/{project_id}/exports/{export_type}",
    response_model=ExportOverseasPlanResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Export an overseas plan artifact",
)
def export_overseas_plan(
    project_id: str,
    export_type: str,
    payload: ExportOverseasPlanRequest,
    request: Request,
    service: OverseasPlanGenerationService = Depends(get_generation_service),
) -> ExportOverseasPlanResponse:
    """Export Word/PPT/Excel artifacts and audit audience as client or internal."""

    try:
        if export_type == "word":
            result = service.export_word(
                WordExportRequest(
                    project_id=project_id,
                    exported_by=payload.exported_by,
                    report_version=payload.report_version,
                    username=payload.username,
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
                )
            )
        elif export_type == "ppt":
            result = service.export_ppt(
                PPTExportRequest(
                    project_id=project_id,
                    exported_by=payload.exported_by,
                    report_version=payload.report_version,
                    username=payload.username,
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
                )
            )
        elif export_type in {"excel", "action_plan"}:
            result = service.export_excel(
                ExcelExportRequest(
                    project_id=project_id,
                    exported_by=payload.exported_by,
                    export_kind=ExcelExportKind.ACTION_PLAN,
                    report_version=payload.report_version,
                    username=payload.username,
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
                )
            )
        elif export_type in {"resources", "resource_list"}:
            result = service.export_excel(
                ExcelExportRequest(
                    project_id=project_id,
                    exported_by=payload.exported_by,
                    export_kind=ExcelExportKind.RESOURCE_LIST,
                    report_version=payload.report_version,
                    username=payload.username,
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
                )
            )
        else:
            raise GenerationServiceError(f"Unsupported export type: {export_type}")
    except Exception as exc:  # noqa: BLE001 - translated at the API boundary.
        _raise_http_error(exc)
    return ExportOverseasPlanResponse(export=asdict(result))
