from __future__ import annotations

import json

from agent_overseas_report.crew import CrewAISettings, create_task_specs, load_packaged_config
from agent_overseas_report.services import GenerationRequest, InMemoryEnterpriseDataRepository, OverseasPlanGenerationService

REQUIRED_SECTIONS = {
    "01_enterprise_diagnosis": {"title": "01 企业诊断"},
    "02_overseas_market_selection": {"title": "02 目标市场选择"},
    "03_entry_mode_design": {"title": "03 进入模式设计"},
    "04_overseas_resource_matching_plan": {"title": "04 资源匹配"},
    "05_exhibition_and_marketing_plan": {"title": "05 展会营销"},
    "06_financing_and_capacity_expansion_plan": {"title": "06 融资扩产"},
    "07_12_24_month_implementation_roadmap": {"title": "07 路线图"},
}


class FakeLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []
        self.config = type("Config", (), {"model": "fake-deepseek"})()

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        self.prompts.append((prompt, system_prompt))
        return self.outputs.pop(0)


def make_repo():
    return InMemoryEnterpriseDataRepository(
        enterprises={
            "ent-1": {
                "id": "ent-1",
                "name": "示例医疗科技",
                "industry": "医疗器械",
                "overseas_customers": ["德国经销商A"],
                "english_materials": ["英文官网", "英文说明书"],
                "team": {"international_members": 3, "languages": ["英语", "德语"], "export_years": 2},
                "finance": {"export_budget": 800000, "credit_line": 1200000},
            }
        },
        products={
            "prod-1": {
                "id": "prod-1",
                "enterprise_id": "ent-1",
                "name": "便携式检测仪",
                "hs_code": "902780",
                "certifications": ["CE", "ISO 13485"],
                "capacity": {"monthly_units": 10000, "lead_time_days": 30},
                "moq": 50,
                "price_band": "USD 200-500",
                "overseas_version": True,
            }
        },
    )


def test_crewai_config_keeps_three_single_responsibility_agents():
    settings = CrewAISettings.from_env()
    task_specs = create_task_specs()
    packaged = load_packaged_config()

    assert set(settings.agent_configs) == {"research", "strategy", "report"}
    assert [task.agent_name for task in task_specs] == ["research", "strategy", "report"]
    assert packaged["feature_flag"] == "ENABLE_CREWAI=true"
    assert len(packaged["agents"]) == 3


def test_generation_service_uses_crewai_only_when_env_flag_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_CREWAI", "true")
    payload = json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)
    llm = FakeLLM(["研究摘要", "策略输出", payload])
    service = OverseasPlanGenerationService(data_repository=make_repo(), llm_client=llm)

    response = service.generate(
        GenerationRequest(
            enterprise_id="ent-1",
            product_ids=["prod-1"],
            selected_industry="医疗器械",
            target_countries=["德国"],
            generated_by="user-1",
        )
    )

    assert response.project["generation_status"] == "completed"
    assert response.project["metadata"]["orchestration"] == "crewai"
    assert response.project["metadata"]["crewai"]["agents"] == ["ResearchAgent", "StrategyAgent", "ReportAgent"]
    assert response.preview == {"sections": REQUIRED_SECTIONS}
    assert len(llm.prompts) == 3
    assert "ResearchAgent" in llm.prompts[0][1]
    assert "StrategyAgent" in llm.prompts[1][1]
    assert "ReportAgent" in llm.prompts[2][0]
