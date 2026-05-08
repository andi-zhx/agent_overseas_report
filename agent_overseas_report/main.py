"""FastAPI application entry point for the agent overseas report backend."""

from __future__ import annotations

from fastapi import FastAPI

from agent_overseas_report.dependencies import create_default_generation_service
from agent_overseas_report.routers import enterprise_master_data_router, health_router, overseas_plans_router
from agent_overseas_report.services import OverseasPlanGenerationService


def create_app(generation_service: OverseasPlanGenerationService | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Agent Overseas Report API",
        description="API backend for enterprise overseas-plan generation.",
        version="0.1.0",
    )
    app.state.overseas_plan_service = generation_service or create_default_generation_service()
    app.include_router(health_router, prefix="/api")
    app.include_router(enterprise_master_data_router, prefix="/api")
    app.include_router(overseas_plans_router, prefix="/api")
    return app


app = create_app()
