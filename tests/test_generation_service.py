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
    assert "context_bundle" in llm.prompts[0][0]
    assert "citations" in llm.prompts[0][0]
    assert response.project["metadata"]["context_bundle"]["enterprise_profile"]["citation_ids"] == ["enterprise_profile:master_data"]


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


def test_generation_service_persists_fallback_status_metadata_and_audit_log():
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

    assert response.project["generation_status"] == "completed"
    assert response.project["metadata"]["json_fallback_used"] is True
    assert response.audit_log["success"] is True
    assert response.preview["version"] == "fallback-v1"


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
    logs = service.store.list_audit_logs()
    assert [log.action_type for log in logs] == [
        "create_plan",
        "ai_generate_plan",
        "regenerate_plan",
        "create_plan",
        "ai_generate_plan",
    ]



def test_audit_log_query_filters_and_sensitive_ai_body_is_not_logged():
    payload = json.dumps({"sections": REQUIRED_SECTIONS, "sensitive_body": "完整AI正文不要进入日志"}, ensure_ascii=False)
    llm = FakeLLM([payload])
    service = OverseasPlanGenerationService(data_repository=make_repo(), llm_client=llm)

    response = service.generate(
        GenerationRequest(
            enterprise_id="ent-1",
            product_ids=["prod-1"],
            selected_industry="医疗器械",
            target_countries=["德国"],
            generated_by="user-1",
            username="张三",
            ip_address="203.0.113.10",
            user_agent="pytest-browser",
        )
    )
    service.view_plan_detail(response.project["id"], user_id="user-1", username="张三")

    from agent_overseas_report.services import AuditLogQuery

    logs = service.list_plan_audit_logs(AuditLogQuery(enterprise_id="ent-1", user_id="user-1", action_type="ai_generate_plan"))

    assert len(logs) == 1
    [log] = logs
    assert log["username"] == "张三"
    assert log["ip_address"] == "203.0.113.10"
    assert log["user_agent"] == "pytest-browser"
    assert log["result_status"] == "success"
    assert log["plan_id"] == response.project["id"]
    assert "完整AI正文不要进入日志" not in json.dumps(log, ensure_ascii=False)


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
    assert export.plan_name == "示例医疗科技企业出海服务正式报告"
    assert export.file_path.endswith(".docx")
    assert (tmp_path / generation.project["id"]).exists()

    import zipfile

    with zipfile.ZipFile(export.file_path) as docx:
        document_xml = docx.read("word/document.xml").decode("utf-8")

    assert "《示例医疗科技企业出海服务正式报告》" in document_xml
    assert "03 执行摘要" in document_xml
    assert "便携式检测仪" in document_xml
    assert "05 出海成熟度诊断" in document_xml
    assert "07 国家优先级矩阵" in document_xml
    assert "15 12-24个月路线图" in document_xml
    assert "17 数据来源" in document_xml
    assert "18 人工复核清单" in document_xml
    assert export.report_version == "client"
    assert export.audit_log_path and export.audit_log_path.endswith("word_export_audit_log.jsonl")

    updated_project = service.store.get_project(generation.project["id"])
    assert updated_project.output_word.file_path == export.file_path
    assert updated_project.output_excel is None

    [audit] = service.store.list_export_audit_logs(generation.project["id"])
    assert audit.exported_by == "user-2"
    assert audit.enterprise_id == "ent-1"
    assert audit.enterprise_name == "示例医疗科技"
    assert audit.plan_name == "示例医疗科技企业出海服务正式报告"
    assert audit.export_type == "Word"
    assert audit.file_path == export.file_path
    assert audit.metadata["report_version"] == "client"
    assert audit.metadata["audit_log_path"] == export.audit_log_path


def test_word_export_internal_version_keeps_quality_score_missing_fields_and_review_flags(tmp_path):
    payload = json.dumps(
        {
            "sections": REQUIRED_SECTIONS,
            "global_manual_review_items": ["需人工复核德国认证周期"],
            "citations": [
                {"source_type": "web", "citation_id": "source-1", "notes": "目标市场资料", "manual_review_required": True}
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
            continue_on_validation_warning=True,
        )
    )

    from agent_overseas_report.services import WordExportRequest

    export = service.export_word(
        WordExportRequest(
            project_id=generation.project["id"],
            exported_by="user-2",
            report_version="internal",
            output_dir=tmp_path,
        )
    )

    import json as json_module
    import zipfile

    with zipfile.ZipFile(export.file_path) as docx:
        document_xml = docx.read("word/document.xml").decode("utf-8")

    assert export.report_version == "internal"
    assert "内部版附录：质量评分与缺失字段" in document_xml
    assert "质量总分" in document_xml
    assert "缺失字段" in document_xml
    assert "需人工复核德国认证周期" in document_xml
    assert "source-1" in document_xml
    audit_path = tmp_path / generation.project["id"] / "word_export_audit_log.jsonl"
    audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
    audit_record = json_module.loads(audit_lines[-1])
    assert audit_record["report_version"] == "internal"
    assert audit_record["exported_by"] == "user-2"

    [audit] = service.store.list_export_audit_logs(generation.project["id"])
    assert audit.metadata["report_version"] == "internal"


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
    assert export.plan_name == "示例医疗科技出海客户汇报稿"
    assert export.file_path.endswith(".pptx")
    assert (tmp_path / generation.project["id"]).exists()

    import zipfile

    with zipfile.ZipFile(export.file_path) as pptx:
        names = pptx.namelist()
        presentation_xml = pptx.read("ppt/presentation.xml").decode("utf-8")
        first_slide_xml = pptx.read("ppt/slides/slide1.xml").decode("utf-8")
        matrix_slide_xml = pptx.read("ppt/slides/slide6.xml").decode("utf-8")
        risk_slide_xml = pptx.read("ppt/slides/slide19.xml").decode("utf-8")

    assert len([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")]) == 20
    assert "Microsoft YaHei" in first_slide_xml
    assert "本次汇报建议以德国为突破口推进示例医疗科技出海增长" in first_slide_xml
    assert "国家优先级矩阵" in matrix_slide_xml
    assert "关键风险应通过红黄绿灯机制明确责任人和止损条件" in risk_slide_xml
    assert "rId20" in presentation_xml

    updated_project = service.store.get_project(generation.project["id"])
    assert updated_project.output_ppt.file_path == export.file_path
    assert updated_project.output_word is None
    assert updated_project.output_excel is None

    [audit] = service.store.list_export_audit_logs(generation.project["id"])
    assert audit.exported_by == "user-2"
    assert audit.enterprise_id == "ent-1"
    assert audit.enterprise_name == "示例医疗科技"
    assert audit.plan_name == "示例医疗科技出海客户汇报稿"
    assert audit.export_type == "PPT"
    assert audit.file_path == export.file_path
    assert export.slide_count == 20
    assert export.report_version == "client"
    assert export.audit_log_path and export.audit_log_path.endswith("ppt_export_audit_log.jsonl")
    assert audit.metadata["report_version"] == "client"
    assert audit.metadata["slide_count"] == 20
    assert audit.metadata["audit_log_path"] == export.audit_log_path


def test_ppt_export_internal_version_supports_theme_logo_footer_and_export_record(tmp_path):
    payload = json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)
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

    export = service.export_ppt(
        PPTExportRequest(
            project_id=generation.project["id"],
            exported_by="user-2",
            report_version="internal",
            logo_text="ACME Logo",
            theme_color="#005BAC",
            footer_text="内部评审材料",
            output_dir=tmp_path,
        )
    )

    import json as json_module
    import zipfile

    with zipfile.ZipFile(export.file_path) as pptx:
        slide1_xml = pptx.read("ppt/slides/slide1.xml").decode("utf-8")
        slide20_xml = pptx.read("ppt/slides/slide20.xml").decode("utf-8")
        theme_xml = pptx.read("ppt/theme/theme1.xml").decode("utf-8")

    assert export.report_version == "internal"
    assert export.slide_count == 20
    assert "ACME Logo" in slide1_xml
    assert "内部评审材料" in slide1_xml
    assert "005BAC" in theme_xml
    assert "内部版需同步跟踪毛利" in slide20_xml
    with open(export.audit_log_path, encoding="utf-8") as file_obj:
        record = json_module.loads(file_obj.readlines()[-1])
    assert record["report_version"] == "internal"
    assert record["slide_count"] == 20
    assert record["logo_text"] == "ACME Logo"
    assert record["theme_color"] == "005BAC"


def test_excel_export_action_plan_creates_xlsx_and_writes_export_audit_log(tmp_path):
    payload = json.dumps(
        {
            "sections": {
                **REQUIRED_SECTIONS,
                "07_12_24_month_implementation_roadmap": {
                    "roadmap": [
                        {
                            "stage": "准入准备期",
                            "time_range": "1-3个月",
                            "core_goal": "完成准入与渠道长名单",
                            "key_actions": ["认证复核", "渠道筛选"],
                            "responsible_party": "海外业务部",
                            "required_resources": ["认证顾问", "德语资料"],
                            "deliverables": ["认证清单", "渠道长名单"],
                            "priority": "高",
                            "status": "待启动",
                            "notes": "优先德国市场",
                        }
                    ]
                },
            }
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

    from agent_overseas_report.services import ExcelExportKind, ExcelExportRequest

    export = service.export_excel(
        ExcelExportRequest(
            project_id=generation.project["id"],
            exported_by="user-2",
            export_kind=ExcelExportKind.ACTION_PLAN,
            output_dir=tmp_path,
        )
    )

    assert export.export_type == "Excel"
    assert export.export_kind == "action_plan"
    assert export.sheet_name == "12-24个月行动计划"
    assert export.file_path.endswith(".xlsx")
    assert export.headers == ["阶段", "时间范围", "核心目标", "关键动作", "负责人", "所需资源", "交付物", "优先级", "状态", "备注"]
    assert export.rows[0]["阶段"] == "准入准备期"
    assert export.rows[0]["关键动作"] == "认证复核；渠道筛选"

    import zipfile

    expected_sheets = [
        "企业基础信息",
        "产品基础信息",
        "目标国家评分矩阵",
        "渠道资源清单",
        "展会与活动计划",
        "认证与合规事项",
        "预算测算",
        "KPI跟踪表",
        "12-24个月行动计划",
        "风险清单",
        "数据来源",
        "人工复核清单",
        "导出记录",
    ]
    assert export.sheet_names == expected_sheets
    assert export.sheets["预算测算"]["headers"] == ["预算项目", "国家/地区", "阶段", "假设", "金额", "币种", "负责人", "备注"]
    assert export.sheets["KPI跟踪表"]["headers"] == ["KPI指标", "目标值", "当前值", "数据来源", "统计周期", "负责人", "状态", "备注"]

    with zipfile.ZipFile(export.file_path) as xlsx:
        workbook_xml = xlsx.read("xl/workbook.xml").decode("utf-8")
        action_sheet_xml = xlsx.read("xl/worksheets/sheet9.xml").decode("utf-8")
        styles_xml = xlsx.read("xl/styles.xml").decode("utf-8")

    for sheet_name in expected_sheets:
        assert sheet_name in workbook_xml
    assert "阶段" in action_sheet_xml
    assert "准入准备期" in action_sheet_xml
    assert "autoFilter" in action_sheet_xml
    assert "customWidth" in action_sheet_xml
    assert "Microsoft YaHei" in styles_xml

    updated_project = service.store.get_project(generation.project["id"])
    assert updated_project.output_excel.file_path == export.file_path
    assert updated_project.output_word is None
    assert updated_project.output_ppt is None

    [audit] = service.store.list_export_audit_logs(generation.project["id"])
    assert audit.exported_by == "user-2"
    assert audit.enterprise_id == "ent-1"
    assert audit.enterprise_name == "示例医疗科技"
    assert audit.plan_name == "示例医疗科技项目执行管理总表"
    assert audit.export_type == "Excel"
    assert audit.file_path == export.file_path


def test_excel_export_resource_list_uses_placeholder_for_missing_resource_name(tmp_path):
    payload = json.dumps(
        {
            "sections": {
                **REQUIRED_SECTIONS,
                "04_overseas_resource_matching_plan": {
                    "resources": [
                        {
                            "resource_type": "渠道资源",
                            "country_region": "德国",
                            "suggested_contact": "医疗器械经销商负责人",
                            "purpose": "验证本地渠道覆盖能力",
                            "priority": "高",
                            "stage": "准入准备期",
                            "materials": ["英文产品手册", "CE证书"],
                            "current_status": "待联系",
                            "notes": "AI未给出具体机构名称",
                        }
                    ]
                },
            }
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

    from agent_overseas_report.services import ExcelExportRequest

    export = service.export_excel(
        ExcelExportRequest(
            project_id=generation.project["id"],
            exported_by="user-2",
            export_kind="resource_list",
            output_dir=tmp_path,
        )
    )

    assert export.export_type == "Excel"
    assert export.export_kind == "resource_list"
    assert export.sheet_name == "渠道资源清单"
    assert export.headers == ["资源类型", "国家/地区", "资源名称", "建议对接对象", "对接目的", "优先级", "所属阶段", "需要准备的材料", "当前状态", "备注"]
    assert export.rows[0]["资源名称"] == "待补充/需人工确认"
    assert export.rows[0]["需要准备的材料"] == "英文产品手册；CE证书"

    import zipfile

    with zipfile.ZipFile(export.file_path) as xlsx:
        sheet_xml = xlsx.read("xl/worksheets/sheet4.xml").decode("utf-8")

    assert "待补充/需人工确认" in sheet_xml
    assert "autoFilter" in sheet_xml
    assert "渠道资源清单" not in sheet_xml  # sheet title is in workbook.xml; sheet cells remain pure data table.

    updated_project = service.store.get_project(generation.project["id"])
    assert updated_project.output_excel.file_path == export.file_path
    [audit] = service.store.list_export_audit_logs(generation.project["id"])
    assert audit.plan_name == "示例医疗科技项目执行管理总表"
    assert audit.export_type == "Excel"

def test_content_versions_track_ai_edit_restore_and_final_version(tmp_path):
    first_payload = json.dumps({"sections": {**REQUIRED_SECTIONS, "01_enterprise_diagnosis": {"title": "AI初版诊断"}}}, ensure_ascii=False)
    regenerated_payload = json.dumps({"sections": {**REQUIRED_SECTIONS, "01_enterprise_diagnosis": {"title": "重新生成诊断"}}}, ensure_ascii=False)
    llm = FakeLLM([first_payload, regenerated_payload])
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
    second = service.regenerate(first.project["id"], generated_by="user-2", extra_context={"reason": "更新诊断"})
    edited = {"sections": {**REQUIRED_SECTIONS, "01_enterprise_diagnosis": {"title": "用户编辑诊断"}}}
    service.update_generated_content(second.project["id"], result=edited, edited_by="user-3")

    history = service.list_versions(first.project["id"])

    assert [version["version_number"] for version in history.versions] == [1, 2, 3]
    assert [version["generation_source"] for version in history.versions] == ["AI生成", "重新生成", "用户编辑"]
    assert history.versions[0]["content_json"]["sections"]["01_enterprise_diagnosis"]["title"] == "AI初版诊断"

    restored = service.restore_version(second.project["id"], 1, restored_by="user-4")
    assert restored.result["sections"]["01_enterprise_diagnosis"]["title"] == "AI初版诊断"
    final_version = service.mark_final_version(second.project["id"], 2, finalized_by="user-5")
    assert final_version["is_final"] is True

    from agent_overseas_report.services import WordExportRequest

    export = service.export_word(WordExportRequest(project_id=second.project["id"], exported_by="user-6", output_dir=tmp_path))

    import zipfile

    with zipfile.ZipFile(export.file_path) as docx:
        document_xml = docx.read("word/document.xml").decode("utf-8")

    assert "重新生成诊断" in document_xml
    assert "用户编辑诊断" not in document_xml


def test_generation_service_falls_back_when_json_repair_fails():
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

    assert response.project["generation_status"] == "completed"
    assert response.project["metadata"]["json_fallback_used"] is True
    assert response.preview["version"] == "fallback-v1"
    assert response.preview["sections"]["04_overseas_resource_matching_plan"]["resources"][0]["resource_name"] == "待补充/需人工确认"
    assert any("需人工复核" in item for item in response.preview["global_manual_review_items"])


def test_generation_service_safety_guards_mark_dynamic_info_and_sanitize_unverified_resources():
    payload = json.dumps(
        {
            "sections": {
                **REQUIRED_SECTIONS,
                "02_overseas_market_selection": {
                    "title": "02 海外市场选择",
                    "entry_reasons_by_country": [
                        {
                            "country": "德国",
                            "entry_reasons": ["德国医疗器械市场规模持续增长"],
                            "manual_review_notes": [],
                        }
                    ],
                },
                "04_overseas_resource_matching_plan": {
                    "title": "04 资源匹配",
                    "resources": [
                        {
                            "resource_type": "渠道代理商",
                            "country_region": "德国",
                            "resource_name": "不存在的代理商A",
                            "contact_email": "fake@example.com",
                            "website_url": "https://fake.example.com",
                            "purpose": "渠道验证",
                        }
                    ],
                },
            }
        },
        ensure_ascii=False,
    )
    llm = FakeLLM([payload])
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

    market_reason = response.preview["sections"]["02_overseas_market_selection"]["entry_reasons_by_country"][0]["entry_reasons"][0]
    resource = response.preview["sections"]["04_overseas_resource_matching_plan"]["resources"][0]
    assert market_reason.endswith("（需人工复核）")
    assert resource["resource_name"] == "待补充/需人工确认"
    assert resource["contact_email"] == "需人工确认"
    assert resource["website_url"] == "需人工确认"
    assert "未在资源库中核验" in resource["notes"]
    assert "不存在的代理商A" not in json.dumps(response.preview, ensure_ascii=False)


def test_all_core_audit_actions_are_recorded_without_sensitive_body(tmp_path):
    first_payload = json.dumps({"sections": REQUIRED_SECTIONS, "sensitive_body": "完整敏感正文"}, ensure_ascii=False)
    regenerated_payload = json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)
    llm = FakeLLM([first_payload, regenerated_payload])
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
    service.view_plan_detail(generation.project["id"], user_id="user-1")
    regenerated = service.regenerate(generation.project["id"], generated_by="user-2")
    service.update_generated_content(regenerated.project["id"], result={"sections": REQUIRED_SECTIONS, "sensitive_body": "编辑后敏感正文"}, edited_by="user-3")

    from agent_overseas_report.services import ExcelExportKind, ExcelExportRequest, PPTExportRequest, WordExportRequest

    service.export_word(WordExportRequest(project_id=regenerated.project["id"], exported_by="user-4", output_dir=tmp_path))
    service.export_ppt(PPTExportRequest(project_id=regenerated.project["id"], exported_by="user-4", output_dir=tmp_path))
    service.export_excel(ExcelExportRequest(project_id=regenerated.project["id"], exported_by="user-4", export_kind=ExcelExportKind.ACTION_PLAN, output_dir=tmp_path))
    service.export_excel(ExcelExportRequest(project_id=regenerated.project["id"], exported_by="user-4", export_kind=ExcelExportKind.RESOURCE_LIST, output_dir=tmp_path))

    logs = [log.to_dict() for log in service.store.list_audit_logs()]
    actions = [log["action_type"] for log in logs]
    for expected in [
        "create_plan",
        "ai_generate_plan",
        "view_plan_detail",
        "regenerate_plan",
        "edit_ai_content",
        "export_word",
        "export_ppt",
        "export_excel_action_plan",
        "export_resource_list",
    ]:
        assert expected in actions
    serialized_logs = json.dumps(logs, ensure_ascii=False)
    assert "完整敏感正文" not in serialized_logs
    assert "编辑后敏感正文" not in serialized_logs


class FakeKnowledgeRetriever:
    def __init__(self) -> None:
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {
                "chunk_id": "chunk-1",
                "text": "德国医疗器械渠道以本地经销商和 CE 认证资料为核心。",
                "file_name": "germany-market.txt",
                "page_number": None,
                "sheet_name": None,
                "slide_number": None,
                "relevance_score": 0.92,
                "metadata": {"country": "德国", "enterprise_id": "ent-1"},
            }
        ]


def test_generation_prompt_includes_retrieved_context_without_replacing_main_flow():
    llm = FakeLLM([json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)])
    retriever = FakeKnowledgeRetriever()
    service = OverseasPlanGenerationService(data_repository=make_repo(), llm_client=llm, knowledge_retriever=retriever)

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
    assert retriever.calls[0]["enterprise_id"] == "ent-1"
    assert retriever.calls[0]["product_id"] == "prod-1"
    assert retriever.calls[0]["industry"] == "医疗器械"
    assert retriever.calls[0]["country"] == "德国"
    assert "retrieved_context" in llm.prompts[0][0]
    assert "germany-market.txt" in llm.prompts[0][0]
    assert "RAG 只作为上下文增强" in llm.prompts[0][0]
    assert response.project["metadata"]["retrieved_context"][0]["chunk_id"] == "chunk-1"


class FakeWebResearchService:
    def __init__(self):
        self.requests = []

    def research(self, request):
        from agent_overseas_report.services.web_research_service import WebResearchResult, WebResearchSource
        from agent_overseas_report.models.overseas_generation import utc_now

        self.requests.append(request)
        now = utc_now()
        return WebResearchResult(
            sources=[
                WebResearchSource(
                    id="wrs-1",
                    query="德国 医疗器械 market size official report",
                    title="Official medical devices market report",
                    url="https://trade.gov/medical-devices",
                    snippet="Public source snippet",
                    source_domain="trade.gov",
                    publish_date="2026-01-01",
                    retrieved_at=now,
                    reliability_score=0.95,
                    source_type="official_government_or_multilateral",
                    related_enterprise_id="ent-1",
                    related_product_id=None,
                    related_country="德国",
                    related_industry="医疗器械",
                )
            ],
            manual_review_items=[],
            retrieved_at=now,
        )


def test_generation_service_runs_web_research_when_local_context_is_insufficient():
    llm = FakeLLM([json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)])
    web_research = FakeWebResearchService()
    service = OverseasPlanGenerationService(data_repository=make_repo(), llm_client=llm, web_research_service=web_research)

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
    assert len(web_research.requests) == 1
    assert response.project["metadata"]["web_research"]["source_count"] == 1
    assert "trade.gov" in llm.prompts[0][0]
    assert "retrieved_at" in llm.prompts[0][0]


def test_generation_service_automatically_scores_report_quality() -> None:
    llm = FakeLLM([json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)])
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

    quality_review = response.project["metadata"]["quality_review"]
    assert quality_review["total_score"] < 75
    assert quality_review["status"] in {"needs_revision", "failed_quality_check"}
    assert quality_review["issues"]
    assert quality_review["suggestions"]
    assert response.project["metadata"]["quality_status"] == quality_review["status"]
    assert service.get_report_quality_score(response.project["id"])["id"] == quality_review["id"]
