from pathlib import Path


WORKBENCH = Path("frontend/src/pages/OverseasPlanWorkbench.tsx")
README = Path("frontend/src/pages/overseas-plan-workbench/README.md")


def test_workbench_exposes_required_controls_and_sections():
    source = WORKBENCH.read_text(encoding="utf-8")

    required_labels = [
        "企业选择器",
        "产品多选器",
        "目标国家选择器",
        "行业选择器",
        "基础版",
        "标准版",
        "投资分析师版",
        "启用本地知识库",
        "启用网络研究",
        "允许缺失字段继续生成",
        "生成方案",
        "生成进度",
        "报告结果预览 / 人工编辑",
        "生成前缺失信息提醒",
        "数据来源展示",
        "质量评分展示",
        "查看版本记录",
        "导出Word方案",
        "导出PPT方案",
        "导出Excel行动计划表",
        "审计日志入口",
    ]

    for label in required_labels:
        assert label in source


def test_workbench_default_generation_uses_backend_api_not_local_report_logic():
    source = WORKBENCH.read_text(encoding="utf-8")

    assert "/api/overseas-plans/generations" in source
    assert "report_depth" in source
    assert "use_local_knowledge_base" in source
    assert "use_web_research" in source
    assert "buildPreviewPlan" not in source


def test_workbench_readme_contains_manual_test_steps():
    readme = README.read_text(encoding="utf-8")

    assert "## 手动测试步骤" in readme
    assert "前端只负责收集参数" in readme
    assert "POST /api/overseas-plans/generations" in readme
