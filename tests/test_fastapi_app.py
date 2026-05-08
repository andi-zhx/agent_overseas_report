from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from agent_overseas_report.main import create_app
from agent_overseas_report.services import InMemoryEnterpriseDataRepository, OverseasPlanGenerationService


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

    def __init__(self) -> None:
        self.prompts: list[tuple[str, str | None]] = []

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        self.prompts.append((prompt, system_prompt))
        return json.dumps({"sections": REQUIRED_SECTIONS}, ensure_ascii=False)


def make_service() -> OverseasPlanGenerationService:
    repo = InMemoryEnterpriseDataRepository(
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
    return OverseasPlanGenerationService(data_repository=repo, llm_client=FakeLLM())


def test_health_check() -> None:
    client = TestClient(create_app(generation_service=make_service()))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agent_overseas_report"}


def test_generate_detail_versions_regenerate_and_finalize_flow() -> None:
    client = TestClient(create_app(generation_service=make_service()))

    generate_response = client.post(
        "/api/overseas-plans/generate",
        json={
            "enterprise_id": "ent-1",
            "product_ids": ["prod-1"],
            "selected_industry": "医疗器械",
            "target_countries": ["德国"],
            "generated_by": "user-1",
        },
    )
    assert generate_response.status_code == 200
    generated = generate_response.json()
    project_id = generated["project"]["id"]
    assert generated["project"]["generation_status"] == "completed"
    assert generated["preview"] == {"sections": REQUIRED_SECTIONS}

    detail_response = client.get(f"/api/overseas-plans/{project_id}", params={"viewed_by": "user-1"})
    assert detail_response.status_code == 200
    assert detail_response.json()["project"]["id"] == project_id

    versions_response = client.get(f"/api/overseas-plans/{project_id}/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert versions["current_version_number"] == 1
    assert len(versions["versions"]) == 1

    finalize_response = client.post(
        f"/api/overseas-plans/{project_id}/finalize",
        json={"version_number": 1, "finalized_by": "user-1"},
    )
    assert finalize_response.status_code == 200
    assert finalize_response.json()["version"]["is_final"] is True

    regenerate_response = client.post(
        f"/api/overseas-plans/{project_id}/regenerate",
        json={"generated_by": "user-2", "extra_context": {"reason": "更新策略"}},
    )
    assert regenerate_response.status_code == 200
    regenerated = regenerate_response.json()
    assert regenerated["project"]["id"] != project_id
    assert regenerated["project"]["metadata"]["extra_context"]["regenerated_from_project_id"] == project_id


def test_knowledge_file_upload_list_get_delete_flow(tmp_path) -> None:
    pytest.importorskip("sqlalchemy")
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from agent_overseas_report.database import create_session_factory, initialize_database
    from agent_overseas_report.knowledge_base.local_files import KnowledgeBaseService, SQLAlchemyKnowledgeBaseRepository

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    initialize_database(engine)
    knowledge_service = KnowledgeBaseService(
        SQLAlchemyKnowledgeBaseRepository(create_session_factory(engine)), tmp_path / "uploads"
    )
    client = TestClient(create_app(generation_service=make_service(), knowledge_base_service=knowledge_service))

    response = client.post(
        "/api/knowledge/files/upload",
        data={
            "enterprise_id": "ent-1",
            "product_id": "prod-1",
            "industry": "医疗器械",
            "country": "德国",
            "source_type": "product_material",
            "metadata_json": '{"language":"zh-CN"}',
        },
        files={"file": ("product.md", "# 产品资料\n便携式检测仪适合德国渠道。".encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["file_type"] == "markdown"
    assert uploaded["parsed_status"] == "parsed"
    assert uploaded["metadata"] == {"language": "zh-CN"}
    assert uploaded["chunks"][0]["text"].startswith("# 产品资料")

    list_response = client.get("/api/knowledge/files", params={"enterprise_id": "ent-1"})
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == uploaded["id"]
    assert list_response.json()[0]["chunks"] == []

    detail_response = client.get(f"/api/knowledge/files/{uploaded['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["chunks"][0]["token_count"] > 0

    delete_response = client.delete(f"/api/knowledge/files/{uploaded['id']}")
    assert delete_response.status_code == 200
    assert client.get(f"/api/knowledge/files/{uploaded['id']}").status_code == 404


def test_knowledge_embed_and_search_api(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from agent_overseas_report.database import create_session_factory, initialize_database
    from agent_overseas_report.knowledge_base.local_files import KnowledgeBaseService, SQLAlchemyKnowledgeBaseRepository
    from agent_overseas_report.knowledge_base.rag import HashingEmbeddingService, LocalFAISSVectorStore

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    initialize_database(engine)
    knowledge_service = KnowledgeBaseService(
        SQLAlchemyKnowledgeBaseRepository(create_session_factory(engine)),
        tmp_path / "uploads",
        embedding_service=HashingEmbeddingService(dimensions=64),
        vector_store=LocalFAISSVectorStore(tmp_path / "vectors"),
    )
    client = TestClient(create_app(generation_service=make_service(), knowledge_base_service=knowledge_service))
    source = tmp_path / "kb.txt"
    source.write_text("德国医疗器械市场需要 CE 认证和经销商网络。", encoding="utf-8")

    with source.open("rb") as file_obj:
        upload_response = client.post(
            "/api/knowledge/files/upload",
            files={"file": ("kb.txt", file_obj, "text/plain")},
            data={"enterprise_id": "ent-1", "product_id": "prod-1", "industry": "医疗器械", "country": "德国"},
        )
    file_id = upload_response.json()["id"]
    embed_response = client.post(f"/api/knowledge/files/{file_id}/embed")
    search_response = client.post(
        "/api/knowledge/search",
        json={
            "query": "德国 CE 认证",
            "enterprise_id": "ent-1",
            "product_id": "prod-1",
            "industry": "医疗器械",
            "country": "德国",
            "top_k": 5,
        },
    )
    empty_response = client.post("/api/knowledge/search", json={"query": "德国", "enterprise_id": "missing", "top_k": 5})

    assert upload_response.status_code == 201
    assert embed_response.status_code == 200
    assert embed_response.json()["embedded_chunk_count"] == 1
    assert search_response.status_code == 200
    [result] = search_response.json()["results"]
    assert result["file_name"] == "kb.txt"
    assert result["metadata"]["country"] == "德国"
    assert empty_response.status_code == 200
    assert empty_response.json() == {"results": []}
