"""Health-check routes for the FastAPI application."""

from __future__ import annotations

from fastapi import APIRouter

from agent_overseas_report.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, summary="Health check")
def health_check() -> HealthResponse:
    """Return API liveness status."""

    return HealthResponse(status="ok", service="agent_overseas_report")
