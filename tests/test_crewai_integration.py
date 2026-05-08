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


def test_crewai_config_defines_complete_enterprise_agents():
    settings = CrewAISettings.from_env()
    task_specs = create_task_specs()
    packaged = load_packaged_config()

    expected_agents = [
        "company_diagnosis",
        "market_research",
        "channel_strategy",
        "resource_matching",
        "financial_planning",
        "risk_compliance",
        "report_writer",
        "quality_review",
    ]

    assert list(settings.agent_configs) == expected_agents
    assert [task.agent_name for task in task_specs] == expected_agents
    assert [task.save_key for task in task_specs] == packaged["tasks"]
    assert packaged["feature_flag"] == "ENABLE_CREWAI=true"
    assert len(packaged["agents"]) == 8
    for config in settings.agent_configs.values():
        assert config.role.endswith("Agent")
        assert config.goal
        assert config.backstory
        assert config.input_spec
        assert config.output_spec
        assert any("不得编造数据" in constraint for constraint in config.constraints)
        assert any("citations" in constraint for constraint in config.constraints)


def test_generation_service_uses_crewai_only_when_env_flag_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_CREWAI", "true")
    payload = json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)
    llm = FakeLLM([
        "企业诊断",
        "市场研究",
        "渠道策略",
        "资源匹配",
        "财务规划",
        "风险合规",
        payload,
        json.dumps({"status": "revision_required", "issues": ["缺少来源"], "required_revisions": ["补充 citations"]}, ensure_ascii=False),
    ])
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
    assert response.project["metadata"]["crewai"]["agents"] == [
        "CompanyDiagnosisAgent",
        "MarketResearchAgent",
        "ChannelStrategyAgent",
        "ResourceMatchingAgent",
        "FinancialPlanningAgent",
        "RiskComplianceAgent",
        "ReportWriterAgent",
        "QualityReviewAgent",
    ]
    assert response.project["metadata"]["crewai_quality_status"] == "revision_required"
    assert set(response.project["metadata"]["crewai_step_outputs"]) == {
        "company_diagnosis",
        "market_research",
        "channel_strategy",
        "resource_matching",
        "financial_planning",
        "risk_compliance",
        "report_writing",
        "quality_review",
    }
    assert response.preview == {"sections": REQUIRED_SECTIONS}
    assert len(llm.prompts) == 8
    assert "CompanyDiagnosisAgent" in llm.prompts[0][1]
    assert "ContextBundle" in llm.prompts[0][0]
    assert "不得编造数据" in llm.prompts[0][0]
    assert "citations" in llm.prompts[0][0]
    assert "不得自行访问数据库" in llm.prompts[0][0]
    assert "QualityReviewAgent" in llm.prompts[7][1]
    assert "revision_required" in llm.prompts[7][0]
