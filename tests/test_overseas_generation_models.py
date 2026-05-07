from __future__ import annotations

from agent_overseas_report.models import (
    COUNTRY_SELECTION_DIMENSIONS,
    MATURITY_SCORE_WEIGHTS,
    CountryDimensionScore,
    CountryPriorityMatrixItem,
    GeneratedFileRef,
    GenerationProject,
    GenerationStatus,
    MaturityAssessment,
    MaturityDimensionScore,
    MaturityLevel,
    OverseasGenerationResult,
    OverseasResource,
    ResourceCategory,
    ResourceSubType,
    infer_maturity_level,
)


def test_maturity_weights_total_one_hundred():
    assert sum(MATURITY_SCORE_WEIGHTS.values()) == 100
    assert MATURITY_SCORE_WEIGHTS == {
        "product_internationalization": 20,
        "overseas_channel_foundation": 20,
        "english_material_completeness": 10,
        "certification_status": 15,
        "supply_chain_stability": 15,
        "team_internationalization": 10,
        "capital_capacity": 10,
    }


def test_country_selection_dimensions_cover_five_factor_model():
    assert COUNTRY_SELECTION_DIMENSIONS == (
        "market_demand",
        "policy_environment",
        "competitive_environment",
        "channel_maturity",
        "supply_chain_fit",
    )


def test_infer_maturity_level_boundaries():
    assert infer_maturity_level(59.9) == MaturityLevel.BEGINNER
    assert infer_maturity_level(60) == MaturityLevel.GROWTH
    assert infer_maturity_level(80) == MaturityLevel.GLOBAL_LAYOUT


def test_generation_project_serializes_nested_result_for_json_storage():
    maturity = MaturityAssessment(
        total_score=82,
        maturity_level=MaturityLevel.GLOBAL_LAYOUT,
        dimension_scores=[
            MaturityDimensionScore(
                dimension="product_internationalization",
                score=18,
                max_score=20,
                comment="多语言资料和认证准备较完善",
            )
        ],
    )
    result = OverseasGenerationResult(
        maturity_assessment=maturity,
        recommended_target_countries=["DE", "US"],
        country_priority_matrix=[
            CountryPriorityMatrixItem(
                country_code="DE",
                country_name="Germany",
                priority_rank=1,
                total_score=88,
                dimension_scores=[CountryDimensionScore(dimension="market_demand", score=90)],
                recommended_entry_mode="渠道代理 + 展会获客",
            )
        ],
        overseas_resource_matches=[
            OverseasResource(
                id="res-1",
                name="Demo Distributor",
                category=ResourceCategory.CHANNEL,
                subtype=ResourceSubType.DISTRIBUTOR,
                country_code="DE",
            )
        ],
    )
    project = GenerationProject(
        id="project-1",
        enterprise_id="enterprise-1",
        product_ids=["product-1"],
        selected_industry="智能制造",
        target_countries=["DE", "US"],
        generation_status=GenerationStatus.COMPLETED,
        final_score=82,
        maturity_level=MaturityLevel.GLOBAL_LAYOUT,
        output_word=GeneratedFileRef(url="https://example.com/report.docx", file_path="reports/report.docx"),
        result=result,
    )

    payload = project.to_dict()

    assert payload["generation_status"] == "completed"
    assert payload["maturity_level"] == "全球化布局型"
    assert payload["output_word"] == {
        "url": "https://example.com/report.docx",
        "file_path": "reports/report.docx",
    }
    assert payload["result"]["maturity_assessment"]["maturity_level"] == "全球化布局型"
    assert payload["result"]["overseas_resource_matches"][0]["category"] == "channel"
    assert payload["created_at"].endswith("+00:00")
