from __future__ import annotations

import json

from agent_overseas_report.services import (
    GenerationRequest,
    InMemoryEnterpriseDataRepository,
    OverseasPlanGenerationService,
    assess_generation_readiness,
)


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


def test_readiness_groups_missing_fields_and_marks_not_recommended():
    report = assess_generation_readiness(
        {
            "enterprise": {"industry": "医疗器械"},
            "products": [{"hs_code": "902780"}],
            "target_markets": [],
        }
    )

    assert report.status.value == "不建议生成"
    assert report.should_popup is True
    assert report.manual_review_required is True
    assert set(report.critical_missing_fields) == {"企业名称", "产品名称", "目标国家"}
    categories = {item.category: item.fields for item in report.missing_categories}
    assert "企业层面" in categories
    assert "产品层面" in categories
    assert "出海目标层面" in categories
    assert "不得编造" in report.prompt_instruction


def test_generation_can_continue_with_severe_missing_and_passes_gaps_to_prompt():
    repo = InMemoryEnterpriseDataRepository(
        enterprises={"ent-1": {"id": "ent-1", "industry": "医疗器械"}},
        products={"prod-1": {"id": "prod-1", "enterprise_id": "ent-1", "hs_code": "902780"}},
    )
    llm = FakeLLM([json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)])
    service = OverseasPlanGenerationService(data_repository=repo, llm_client=llm)

    response = service.generate(
        GenerationRequest(
            enterprise_id="ent-1",
            product_ids=["prod-1"],
            selected_industry="医疗器械",
            target_countries=[],
            generated_by="user-1",
            continue_on_validation_warning=True,
        )
    )

    assert response.project["generation_status"] == "completed"
    readiness = response.project["metadata"]["generation_readiness"]
    assert readiness["status"] == "不建议生成"
    assert response.preview["data_quality_review"]["manual_review_required"] is True
    assert "需人工补充/复核" in response.preview["global_manual_review_items"][-1]
    assert "generation_readiness" in llm.prompts[0][0]
    assert "不得编造" in llm.prompts[0][0]


def test_generation_blocks_severe_missing_without_continue_flag():
    repo = InMemoryEnterpriseDataRepository(
        enterprises={"ent-1": {"id": "ent-1", "industry": "医疗器械"}},
        products={"prod-1": {"id": "prod-1", "enterprise_id": "ent-1"}},
    )
    llm = FakeLLM([json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)])
    service = OverseasPlanGenerationService(data_repository=repo, llm_client=llm)

    response = service.generate(
        GenerationRequest(
            enterprise_id="ent-1",
            product_ids=["prod-1"],
            selected_industry="医疗器械",
            target_countries=[],
            generated_by="user-1",
        )
    )

    assert response.project["generation_status"] == "failed"
    assert "不建议直接生成" in response.project["error_reason"]
    assert llm.prompts == []
