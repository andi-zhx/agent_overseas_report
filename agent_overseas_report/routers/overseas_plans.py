"""Overseas-plan API routes backed by ``OverseasPlanGenerationService``."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agent_overseas_report.schemas import (
    ErrorResponse,
    FinalizeOverseasPlanRequest,
    FinalizeOverseasPlanResponse,
    GenerateOverseasPlanRequest,
    OverseasPlanDetailResponse,
    OverseasPlanGenerationResponse,
    OverseasPlanVersionListResponse,
    RegenerateOverseasPlanRequest,
)
from agent_overseas_report.services import DataNotFoundError, GenerationRequest, GenerationServiceError, OverseasPlanGenerationService
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
