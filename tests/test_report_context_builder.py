from __future__ import annotations

from agent_overseas_report.services import ReportContextBuilder


def test_report_context_builder_builds_citation_aware_bundle() -> None:
    builder = ReportContextBuilder()

    bundle = builder.build(
        enterprise_data={
            "enterprise": {"id": "ent-1", "name": "示例医疗科技", "industry": "医疗器械"},
            "products": [{"id": "prod-1", "name": "便携式检测仪", "hs_code": "902780"}],
        },
        user_parameters={"enterprise_id": "ent-1", "target_countries": ["德国"]},
        local_chunks=[{"chunk_id": "chunk-1", "title": "德国医疗器械准入", "source_uri": "kb://germany", "relevance_score": 0.91}],
        web_research_sources=[
            {
                "source_kind": "public_web",
                "title": "Germany medical devices import rules",
                "url": "https://trade.gov/germany-medical-devices",
                "source_domain": "trade.gov",
                "retrieved_at": "2026-05-08T00:00:00+00:00",
                "reliability_score": 0.95,
            }
        ],
        rule_engine_outputs={"maturity_assessment": {"total_score": 80}},
        missing_field_analysis={
            "status": "可生成但质量较低",
            "manual_review_required": True,
            "critical_missing_fields": ["出口预算"],
            "missing_categories": [{"category": "企业层面", "fields": ["出口预算"]}],
            "message": "部分信息缺失",
            "prompt_instruction": "不得编造缺失字段",
        },
    )
    payload = bundle.to_dict()

    assert payload["enterprise_profile"]["citation_ids"] == ["enterprise_profile:master_data"]
    assert payload["product_profile"][0]["citation_ids"] == ["product_profile:prod-1"]
    assert payload["retrieved_local_chunks"][0]["chunk_id"] == "chunk-1"
    assert payload["web_research_sources"][0]["url"].startswith("https://trade.gov")
    assert payload["rule_engine_outputs"]["maturity_assessment"]["total_score"] == 80
    assert payload["missing_fields"] == [{"category": "企业层面", "field": "出口预算", "severity": "可生成但质量较低"}]
    citation_ids = {item["citation_id"] for item in payload["citations"]}
    assert {
        "enterprise_profile:master_data",
        "product_profile:prod-1",
        "local_knowledge:chunk-1",
        "web_research:1",
        "rule_engine:overseas_rule_engine",
        "missing_fields:generation_readiness",
    }.issubset(citation_ids)
    assert "存在缺失字段" in " ".join(payload["data_quality_warnings"])
