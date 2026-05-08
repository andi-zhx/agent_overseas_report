from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from agent_overseas_report.database import (
    SQLAlchemyEnterpriseRepository,
    SQLiteGenerationRepository,
    create_session_factory,
    initialize_database,
)
from agent_overseas_report.models import GenerationProject, GenerationSource, GenerationStatus, PlanContentVersion
from agent_overseas_report.services import OverseasPlanAuditLog, OverseasPlanGenerationService

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
    config = type("Config", (), {"model": "fake-deepseek"})()

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        import json

        return json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)


def make_repositories() -> tuple[SQLAlchemyEnterpriseRepository, SQLiteGenerationRepository]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    return SQLAlchemyEnterpriseRepository(session_factory), SQLiteGenerationRepository(session_factory)


def test_database_tables_include_required_common_columns() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    initialize_database(engine)

    inspector = inspect(engine)
    expected_tables = {
        "enterprises",
        "products",
        "overseas_generation_projects",
        "overseas_plan_versions",
        "overseas_audit_logs",
        "report_exports",
    }

    assert expected_tables.issubset(set(inspector.get_table_names()))
    for table_name in expected_tables:
        column_names = {column["name"] for column in inspector.get_columns(table_name)}
        assert {"id", "created_at", "updated_at", "status", "metadata"}.issubset(column_names)

    enterprise_columns = {column["name"] for column in inspector.get_columns("enterprises")}
    assert {
        "unified_social_credit_code",
        "enterprise_nature",
        "established_at",
        "region",
        "main_business",
        "core_products",
        "annual_revenue_range",
        "export_experience",
        "current_export_countries",
        "capacity_status",
        "certifications",
        "financing_needs",
        "overseas_goals",
        "investment_profile",
        "market_entry_preferences",
        "channel_requirements",
        "expansion_plan",
    }.issubset(enterprise_columns)

    product_columns = {column["name"] for column in inspector.get_columns("products")}
    assert {
        "product_category",
        "hs_code",
        "application_scenarios",
        "core_selling_points",
        "technical_parameters",
        "price_range",
        "moq",
        "capacity",
        "certifications",
        "target_customers",
        "competitors",
        "export_restrictions",
        "compliance_requirements",
        "investment_highlights",
        "market_entry_notes",
        "channel_fit",
        "financing_expansion_assumptions",
    }.issubset(product_columns)


def test_sqlite_enterprise_repository_round_trips_enterprise_and_products() -> None:
    enterprise_repo, _ = make_repositories()
    enterprise_repo.upsert_enterprise(
        {
            "id": "ent-db",
            "name": "数据库企业",
            "industry": "工业设备",
            "metadata": {"source": "pytest"},
            "team": {"languages": ["英语"]},
        }
    )
    enterprise_repo.upsert_product(
        {
            "id": "prod-db",
            "enterprise_id": "ent-db",
            "name": "测试产品",
            "metadata": {"source": "pytest"},
            "certifications": ["CE"],
        }
    )

    enterprise = enterprise_repo.get_enterprise("ent-db")
    products = enterprise_repo.get_products("ent-db", ["prod-db"])

    assert enterprise["name"] == "数据库企业"
    assert enterprise["metadata"] == {"source": "pytest"}
    assert products[0]["name"] == "测试产品"
    assert products[0]["certifications"] == ["CE"]


def test_sqlite_generation_repository_round_trips_projects_versions_audits_and_exports() -> None:
    _, generation_repo = make_repositories()
    project = GenerationProject(
        id=f"ogp_{uuid4().hex}",
        enterprise_id="ent-db",
        product_ids=["prod-db"],
        selected_industry="工业设备",
        target_countries=["德国"],
        generation_status=GenerationStatus.COMPLETED,
        generated_by="user-1",
        result={"sections": REQUIRED_SECTIONS},
        metadata={"plan_group_id": "plan-group-1", "source": "pytest"},
    )

    saved = generation_repo.save_project(project)
    version = generation_repo.append_content_version(
        PlanContentVersion(
            project_id=saved.id,
            source_project_id=saved.id,
            version_number=generation_repo.next_content_version(saved.id),
            created_by="user-1",
            created_at=datetime.now(timezone.utc),
            generation_source=GenerationSource.AI_GENERATED,
            change_summary="AI生成完成",
            content_json={"sections": REQUIRED_SECTIONS},
            generation_status=GenerationStatus.COMPLETED,
        )
    )
    audit = generation_repo.append_audit_log(
        OverseasPlanAuditLog(
            id=f"opa_{uuid4().hex}",
            user_id="user-1",
            username="张三",
            action_type="export_word",
            enterprise_id="ent-db",
            plan_id=saved.id,
            product_ids=["prod-db"],
            target_countries=["德国"],
            export_type="Word",
            created_at=datetime.now(timezone.utc).isoformat(),
            ip_address="127.0.0.1",
            user_agent="pytest",
            result_status="success",
            file_path="/tmp/report.docx",
            exported_by="user-1",
            exported_at=datetime.now(timezone.utc).isoformat(),
            plan_name="数据库企业出海解决方案",
        )
    )

    loaded = generation_repo.get_project(saved.id)
    versions = generation_repo.list_content_versions(saved.id)
    logs = generation_repo.list_export_audit_logs(saved.id)
    exports = generation_repo.list_report_exports(saved.id)

    assert loaded is not None
    assert loaded.metadata["source"] == "pytest"
    assert loaded.result == {"sections": REQUIRED_SECTIONS}
    assert version.version_number == 1
    assert versions[0].content_json == {"sections": REQUIRED_SECTIONS}
    assert logs[0].id == audit.id
    assert exports[0]["file_path"] == "/tmp/report.docx"


def test_generation_service_can_use_sqlite_repository() -> None:
    enterprise_repo, generation_repo = make_repositories()
    enterprise_repo.upsert_enterprise(
        {
            "id": "ent-1",
            "name": "示例医疗科技",
            "industry": "医疗器械",
            "overseas_customers": ["德国经销商A"],
            "english_materials": ["英文官网", "英文说明书"],
            "team": {"international_members": 3, "languages": ["英语", "德语"], "export_years": 2},
            "finance": {"export_budget": 800000, "credit_line": 1200000},
        }
    )
    enterprise_repo.upsert_product(
        {
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
    )
    service = OverseasPlanGenerationService(data_repository=enterprise_repo, llm_client=FakeLLM(), store=generation_repo)

    from agent_overseas_report.services import GenerationRequest

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
    assert generation_repo.get_project(response.project["id"]) is not None
    assert len(generation_repo.list_content_versions(response.project["id"])) == 1
    assert [log.action_type for log in generation_repo.list_audit_logs(response.project["id"])] == [
        "create_plan",
        "ai_generate_plan",
    ]


def test_knowledge_base_tables_include_file_and_chunk_columns() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    initialize_database(engine)

    inspector = inspect(engine)
    assert {"knowledge_base_files", "knowledge_base_chunks"}.issubset(set(inspector.get_table_names()))

    file_columns = {column["name"] for column in inspector.get_columns("knowledge_base_files")}
    assert {
        "file_name",
        "file_type",
        "file_path",
        "enterprise_id",
        "product_id",
        "industry",
        "country",
        "source_type",
        "uploaded_at",
        "parsed_status",
        "parse_error",
    }.issubset(file_columns)

    chunk_columns = {column["name"] for column in inspector.get_columns("knowledge_base_chunks")}
    assert {
        "file_id",
        "chunk_index",
        "text",
        "page_number",
        "sheet_name",
        "slide_number",
        "token_count",
        "metadata",
    }.issubset(chunk_columns)
