from __future__ import annotations

from agent_overseas_report.services import ReportQualityScoringService


def high_quality_report() -> dict:
    return {
        "sections": {
            "01_enterprise_diagnosis": {"title": "企业诊断", "summary": "优势、短板、产能、认证、团队能力均已分析", "citations": ["enterprise_profile:master_data"]},
            "02_overseas_market_selection": {"title": "市场选择", "detail": "德国市场需求增长，竞争、准入、客户画像完整", "citations": ["web:market-1"]},
            "03_entry_mode_design": {"title": "进入模式", "detail": "经销伙伴+展会获客，下一步行动、负责人和里程碑明确"},
            "05_exhibition_and_marketing_plan": {"title": "展会营销", "detail": "Medica 展会和线上线索获取"},
            "06_financing_and_capacity_expansion_plan": {"title": "融资扩产", "detail": "融资500万元，预算200万元，ROI 18%，回收期18个月，包含假设和敏感性"},
            "07_12_24_month_implementation_roadmap": {"title": "路线图", "detail": "0-6个月、6-12个月、12-24个月里程碑、行动、负责人、KPI"},
            "08_risk_warnings_and_next_steps": {
                "risk_warnings": [
                    {"type": "合规认证", "mitigation": "认证复核"},
                    {"type": "关税汇率", "mitigation": "锁汇预案"},
                    {"type": "物流合同", "mitigation": "备选物流商"},
                ],
                "next_action_checklist": ["确认渠道名单", "启动认证复核"],
            },
        },
        "enterprise_diagnosis": {"strengths": ["CE认证"], "gaps": ["本地售后"], "citations": ["enterprise:1"]},
        "product_competitiveness_analysis": {"summary": "产品竞争力明确"},
        "maturity_assessment": {"total_score": 78},
        "recommended_target_countries": ["德国"],
        "country_priority_matrix": [{"country_name": "德国", "priority_rank": 1, "total_score": 88, "citations": ["web:market-1"]}],
        "recommended_entry_modes": [{"mode": "经销商"}],
        "channel_path_design": [{"action": "签约2家经销商", "owner": "海外销售", "time": "0-6个月"}],
        "overseas_resource_matches": [{"name": "Medica", "citations": ["web:exhibition-1"]}],
        "exhibition_and_marketing_plan": [{"event": "Medica", "budget": "50万元"}],
        "financing_and_capacity_plan": {"budget": "200万元", "funding": "500万元", "assumptions": ["ROI 18%", "回收期18个月"], "citations": ["finance:1"]},
        "implementation_roadmap_12_24_months": [
            {"time": "0-6个月", "actions": ["渠道筛选"], "kpi": "20条线索"},
            {"time": "6-12个月", "actions": ["首批订单"], "kpi": "3个订单"},
            {"time": "12-24个月", "actions": ["本地售后"], "kpi": "收入1000万元"},
        ],
        "risk_warnings": [
            {"type": "合规认证", "mitigation": "认证复核"},
            {"type": "关税汇率", "mitigation": "锁汇预案"},
            {"type": "物流合同", "mitigation": "备选物流商"},
        ],
        "next_action_suggestions": ["确认渠道名单", "启动认证复核"],
    }


def test_report_quality_scoring_service_scores_all_ten_dimensions() -> None:
    service = ReportQualityScoringService()

    score = service.score_report(report=high_quality_report(), project_id="ogp-test", version_number=1, context_bundle={"citations": ["ctx:1"]})

    assert score.total_score >= 75
    assert score.status.value == "passed"
    assert len(score.dimension_scores) == 10
    assert {item.name for item in score.dimension_scores} == {
        "数据完整度",
        "引用来源完整度",
        "市场分析深度",
        "公司诊断深度",
        "渠道方案可执行性",
        "投融资分析深度",
        "风险覆盖度",
        "预算与 KPI 可量化程度",
        "12-24个月路线图清晰度",
        "客户交付可读性",
    }


def test_report_quality_scoring_service_marks_failed_and_returns_revisions() -> None:
    service = ReportQualityScoringService()

    score = service.score_report(report={"sections": {"01_enterprise_diagnosis": {"title": "占位"}}}, project_id="ogp-test")

    assert score.total_score < 60
    assert score.status.value == "failed_quality_check"
    assert score.issues
    assert score.suggestions
