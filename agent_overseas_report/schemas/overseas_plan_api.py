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
