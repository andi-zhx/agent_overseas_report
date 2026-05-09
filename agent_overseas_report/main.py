"""FastAPI application entry point for the agent overseas report backend."""

from __future__ import annotations

from fastapi import FastAPI

from agent_overseas_report.config import AppSettings, configure_logging
from agent_overseas_report.dependencies import create_default_generation_service, create_default_knowledge_base_service
from agent_overseas_report.routers import (
    enterprise_master_data_router,
    health_router,
    knowledge_files_router,
    overseas_plans_router,
)
from agent_overseas_report.knowledge_base.local_files import KnowledgeBaseService
from agent_overseas_report.services import OverseasPlanGenerationService


def create_app(
    generation_service: OverseasPlanGenerationService | None = None,
    knowledge_base_service: KnowledgeBaseService | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = AppSettings.from_env()
    settings.validate()
    configure_logging(settings)

    app = FastAPI(
        title="Agent Overseas Report API",
        description="API backend for enterprise overseas-plan generation.",
        version="0.1.0",
    )
    app.state.settings = settings
    app.state.knowledge_base_service = knowledge_base_service or create_default_knowledge_base_service()
    app.state.overseas_plan_service = generation_service or create_default_generation_service(
        knowledge_retriever=app.state.knowledge_base_service
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(enterprise_master_data_router, prefix="/api")
    app.include_router(overseas_plans_router, prefix="/api")
    app.include_router(knowledge_files_router, prefix="/api")
    return app


app = create_app()
