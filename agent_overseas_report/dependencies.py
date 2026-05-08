"""FastAPI dependency helpers for the overseas-plan API layer."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import Request

from agent_overseas_report.database import (
    SQLAlchemyEnterpriseRepository,
    SQLiteGenerationRepository,
    create_database_engine,
    create_session_factory,
    initialize_database,
    seed_demo_data,
)
from agent_overseas_report.services import DeepSeekLLMService, OverseasPlanGenerationService


REQUIRED_SECTIONS: dict[str, Any] = {
    "01_enterprise_diagnosis": {"title": "01 企业诊断"},
    "02_overseas_market_selection": {"title": "02 目标市场选择"},
    "03_entry_mode_design": {"title": "03 进入模式设计"},
    "04_overseas_resource_matching_plan": {"title": "04 资源匹配"},
    "05_exhibition_and_marketing_plan": {"title": "05 展会营销"},
    "06_financing_and_capacity_expansion_plan": {"title": "06 融资扩产"},
    "07_12_24_month_implementation_roadmap": {"title": "07 路线图"},
}


class DemoLLMClient:
    """Deterministic local LLM adapter for API smoke tests and local demos.

    The API layer still calls ``OverseasPlanGenerationService``; this adapter is
    only the default provider when no ``DEEPSEEK_API_KEY`` is configured.
    """

    config = type("DemoLLMConfig", (), {"model": "demo-local-json"})()

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """Return a minimal valid plan JSON payload accepted by the service."""

        return json.dumps(
            {
                "sections": REQUIRED_SECTIONS,
                "next_action_suggestions": ["补充真实企业和产品数据后接入正式 LLM 生成。"],
            },
            ensure_ascii=False,
        )


def create_default_generation_service() -> OverseasPlanGenerationService:
    """Create the default SQLite-backed generation service for FastAPI.

    The application initializes local SQLite tables on startup and seeds a small
    demo enterprise/product so smoke tests remain runnable without external
    services. Unit tests can still inject ``InMemoryGenerationStore`` explicitly.
    """

    engine = create_database_engine()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    data_repository = SQLAlchemyEnterpriseRepository(session_factory)
    seed_demo_data(data_repository)
    store = SQLiteGenerationRepository(session_factory)
    llm_client = DeepSeekLLMService() if os.getenv("DEEPSEEK_API_KEY") else DemoLLMClient()
    return OverseasPlanGenerationService(data_repository=data_repository, llm_client=llm_client, store=store)


def get_generation_service(request: Request) -> OverseasPlanGenerationService:
    """Return the app-scoped generation service instance."""

    return request.app.state.overseas_plan_service
