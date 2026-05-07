from __future__ import annotations

import json

from agent_overseas_report.services import (
    GenerationRequest,
    InMemoryEnterpriseDataRepository,
    OverseasPlanGenerationService,
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


def test_generation_service_runs_main_flow_and_writes_completed_audit():
    llm = FakeLLM([json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)])
    service = OverseasPlanGenerationService(data_repository=make_repo(), llm_client=llm)

    response = service.generate(
        GenerationRequest(
            enterprise_id="ent-1",
            product_ids=["prod-1"],
            selected_industry="医疗器械",
            target_countries=["德国", "美国"],
            generated_by="user-1",
        )
    )

    assert response.project["generation_status"] == "completed"
    assert response.project["version"] == 1
    assert response.project["final_score"] > 0
    assert response.preview == {"sections": REQUIRED_SECTIONS}
    assert response.audit_log["generated_by"] == "user-1"
    assert response.audit_log["enterprise_id"] == "ent-1"
    assert response.audit_log["product_ids"] == ["prod-1"]
    assert response.audit_log["target_countries"] == ["德国", "美国"]
    assert response.audit_log["success"] is True
    assert "示例医疗科技" in llm.prompts[0][0]
    assert "resource_templates" in llm.prompts[0][0]


def test_generation_service_repairs_invalid_json_once():
    valid = json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)
    llm = FakeLLM(["not-json", valid])
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
    assert response.project["metadata"]["json_repaired"] is True
    assert len(llm.prompts) == 2
    assert "校验失败原因" in llm.prompts[1][0]


def test_generation_service_persists_failed_status_error_and_audit_log():
    llm = FakeLLM(["not-json", "still-not-json"])
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

    assert response.project["generation_status"] == "failed"
    assert "error_reason" in response.project["metadata"]
    assert response.audit_log["success"] is False
    assert "DeepSeek JSON validation failed" in response.audit_log["error_reason"]


def test_regenerate_creates_new_version_without_overwriting_history():
    payload = json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)
    llm = FakeLLM([payload, payload])
    service = OverseasPlanGenerationService(data_repository=make_repo(), llm_client=llm)
    first = service.generate(
        GenerationRequest(
            enterprise_id="ent-1",
            product_ids=["prod-1"],
            selected_industry="医疗器械",
            target_countries=["德国"],
            generated_by="user-1",
        )
    )

    second = service.regenerate(first.project["id"], generated_by="user-2")

    assert first.project["id"] != second.project["id"]
    assert first.project["version"] == 1
    assert second.project["version"] == 2
    assert second.project["metadata"]["extra_context"]["regenerated_from_project_id"] == first.project["id"]
    assert len(service.store.list_audit_logs()) == 2


def test_word_export_creates_docx_and_writes_export_audit_log(tmp_path):
    payload = json.dumps(
        {
            "sections": {
                **REQUIRED_SECTIONS,
                "08_risk_warnings_and_next_steps": {
                    "next_action_checklist": ["确认德国渠道名单", "启动CE认证复核"],
                    "risk_warnings": [{"type": "policy", "description": "关注欧盟医疗器械法规变化"}],
                },
            },
            "country_priority_matrix": [
                {
                    "country_name": "德国",
                    "priority_rank": 1,
                    "total_score": 88,
                    "recommended_entry_mode": "经销代理+展会获客",
                    "key_opportunities": ["医疗器械需求稳定"],
                    "key_risks": ["认证周期较长"],
                }
            ],
            "implementation_roadmap_12_24_months": [
                {
                    "time": "0-6个月",
                    "goal": "完成准入准备",
                    "actions": ["认证复核", "渠道筛选"],
                    "owner": "海外业务部",
                    "deliverables": ["认证清单", "渠道长名单"],
                }
            ],
        },
        ensure_ascii=False,
    )
    llm = FakeLLM([payload])
    service = OverseasPlanGenerationService(data_repository=make_repo(), llm_client=llm)
    generation = service.generate(
        GenerationRequest(
            enterprise_id="ent-1",
            product_ids=["prod-1"],
            selected_industry="医疗器械",
            target_countries=["德国"],
            generated_by="user-1",
        )
    )

    from agent_overseas_report.services import WordExportRequest

    export = service.export_word(
        WordExportRequest(project_id=generation.project["id"], exported_by="user-2", output_dir=tmp_path)
    )

    assert export.export_type == "Word"
    assert export.plan_name == "示例医疗科技企业出海解决方案"
    assert export.file_path.endswith(".docx")
    assert (tmp_path / generation.project["id"]).exists()

    import zipfile

    with zipfile.ZipFile(export.file_path) as docx:
        document_xml = docx.read("word/document.xml").decode("utf-8")

    assert "《示例医疗科技企业出海解决方案》" in document_xml
    assert "01 企业现状诊断" in document_xml
    assert "08 风险提示与下一步建议" in document_xml
    assert "国家优先级矩阵表" in document_xml
    assert "12-24个月实施路线图" in document_xml

    updated_project = service.store.get_project(generation.project["id"])
    assert updated_project.output_word.file_path == export.file_path
    assert updated_project.output_excel is None

    [audit] = service.store.list_export_audit_logs(generation.project["id"])
    assert audit.exported_by == "user-2"
    assert audit.enterprise_id == "ent-1"
    assert audit.enterprise_name == "示例医疗科技"
    assert audit.plan_name == "示例医疗科技企业出海解决方案"
    assert audit.export_type == "Word"
    assert audit.file_path == export.file_path


def test_ppt_export_creates_pptx_and_writes_export_audit_log(tmp_path):
    payload = json.dumps(
        {
            "sections": {
                **REQUIRED_SECTIONS,
                "08_risk_warnings_and_next_steps": {
                    "next_action_checklist": ["确认德国渠道名单", "启动CE认证复核"],
                    "risk_warnings": [{"type": "policy", "description": "关注欧盟医疗器械法规变化"}],
                },
            },
            "country_priority_matrix": [
                {
                    "country_name": "德国",
                    "priority_rank": 1,
                    "total_score": 88,
                    "recommended_entry_mode": "经销代理+展会获客",
                    "key_opportunities": ["医疗器械需求稳定"],
                    "key_risks": ["认证周期较长"],
                }
            ],
            "implementation_roadmap_12_24_months": [
                {
                    "time": "1-3个月",
                    "goal": "完成准入准备",
                    "actions": ["认证复核", "渠道筛选"],
                    "deliverables": ["认证清单", "渠道长名单"],
                }
            ],
        },
        ensure_ascii=False,
    )
    llm = FakeLLM([payload])
    service = OverseasPlanGenerationService(data_repository=make_repo(), llm_client=llm)
    generation = service.generate(
        GenerationRequest(
            enterprise_id="ent-1",
            product_ids=["prod-1"],
            selected_industry="医疗器械",
            target_countries=["德国"],
            generated_by="user-1",
        )
    )

    from agent_overseas_report.services import PPTExportRequest

    export = service.export_ppt(PPTExportRequest(project_id=generation.project["id"], exported_by="user-2", output_dir=tmp_path))

    assert export.export_type == "PPT"
    assert export.plan_name == "示例医疗科技出海解决方案"
    assert export.file_path.endswith(".pptx")
    assert (tmp_path / generation.project["id"]).exists()

    import zipfile

    with zipfile.ZipFile(export.file_path) as pptx:
        names = pptx.namelist()
        presentation_xml = pptx.read("ppt/presentation.xml").decode("utf-8")
        first_slide_xml = pptx.read("ppt/slides/slide1.xml").decode("utf-8")
        matrix_slide_xml = pptx.read("ppt/slides/slide6.xml").decode("utf-8")
        risk_slide_xml = pptx.read("ppt/slides/slide12.xml").decode("utf-8")

    assert len([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")]) == 12
    assert "Microsoft YaHei" in first_slide_xml
    assert "《示例医疗科技出海解决方案》" in first_slide_xml
    assert "国家优先级矩阵" in matrix_slide_xml
    assert "近期应优先控制准入" in risk_slide_xml
    assert "rId12" in presentation_xml

    updated_project = service.store.get_project(generation.project["id"])
    assert updated_project.output_ppt.file_path == export.file_path
    assert updated_project.output_word is None
    assert updated_project.output_excel is None

    [audit] = service.store.list_export_audit_logs(generation.project["id"])
    assert audit.exported_by == "user-2"
    assert audit.enterprise_id == "ent-1"
    assert audit.enterprise_name == "示例医疗科技"
    assert audit.plan_name == "示例医疗科技出海解决方案"
    assert audit.export_type == "PPT"
    assert audit.file_path == export.file_path
