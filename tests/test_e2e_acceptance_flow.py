from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from agent_overseas_report.database import create_session_factory, initialize_database
from agent_overseas_report.knowledge_base.local_files import KnowledgeBaseService, SQLAlchemyKnowledgeBaseRepository
from agent_overseas_report.knowledge_base.rag import HashingEmbeddingService, LocalFAISSVectorStore
from agent_overseas_report.main import create_app
from agent_overseas_report.services import InMemoryEnterpriseDataRepository, OverseasPlanGenerationService

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "e2e"
REPORT_SAMPLE_PATH = Path(__file__).parent / "fixtures" / "investment_grade_overseas_plan_sample.json"


class MockLLM:
    """Deterministic LLM mock that never calls an external provider."""

    config = type("Config", (), {"model": "mock-e2e-local-json"})()

    def __init__(self, report_payload: dict) -> None:
        self.report_payload = report_payload
        self.prompts: list[tuple[str, str | None]] = []

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        self.prompts.append((prompt, system_prompt))
        return json.dumps(self.report_payload, ensure_ascii=False)


class MockWebResearchService:
    """Source-preserving WebResearch mock used by the E2E acceptance flow."""

    def __init__(self) -> None:
        self.requests = []

    def research(self, request):
        from agent_overseas_report.models.overseas_generation import utc_now
        from agent_overseas_report.services.web_research_service import WebResearchResult, WebResearchSource

        self.requests.append(request)
        now = utc_now()
        return WebResearchResult(
            sources=[
                WebResearchSource(
                    id="mock-web-germany-medtech-2026",
                    query="Germany medical devices distributors CE registration market report",
                    title="Mock Germany medical devices market and distributor note",
                    url="https://example.test/research/germany-medtech-2026",
                    snippet="Germany requires CE documentation, local distributor enablement, post-market surveillance and service readiness.",
                    source_domain="example.test",
                    publish_date="2026-01-15",
                    retrieved_at=now,
                    reliability_score=0.91,
                    source_type="mock_public_research",
                    related_enterprise_id=request.enterprise_id,
                    related_product_id=None,
                    related_country="德国",
                    related_industry=request.industry,
                ),
                WebResearchSource(
                    id="mock-web-netherlands-logistics-2026",
                    query="Netherlands medical devices logistics distributor entry",
                    title="Mock Netherlands logistics gateway note",
                    url="https://example.test/research/netherlands-medtech-2026",
                    snippet="The Netherlands can be evaluated as a logistics and distributor coordination hub for EU expansion.",
                    source_domain="example.test",
                    publish_date="2026-02-10",
                    retrieved_at=now,
                    reliability_score=0.86,
                    source_type="mock_public_research",
                    related_enterprise_id=request.enterprise_id,
                    related_product_id=None,
                    related_country="荷兰",
                    related_industry=request.industry,
                ),
            ],
            manual_review_items=["联网研究为 mock 数据，正式交付前需替换为真实来源并复核发布日期。"],
            retrieved_at=now,
        )


def _load_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _make_knowledge_base_service(tmp_path: Path) -> KnowledgeBaseService:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    initialize_database(engine)
    return KnowledgeBaseService(
        repository=SQLAlchemyKnowledgeBaseRepository(create_session_factory(engine)),
        storage_dir=tmp_path / "uploads",
        embedding_service=HashingEmbeddingService(dimensions=96),
        vector_store=LocalFAISSVectorStore(tmp_path / "vectors"),
    )


def _post_upload(client: TestClient, fixture_name: str, *, enterprise_id: str, product_id: str | None, source_type: str) -> dict:
    file_path = FIXTURE_DIR / fixture_name
    with file_path.open("rb") as file_obj:
        response = client.post(
            "/api/knowledge/files/upload",
            data={
                "enterprise_id": enterprise_id,
                "product_id": product_id or "",
                "industry": "医疗器械",
                "country": "德国",
                "source_type": source_type,
                "metadata_json": json.dumps({"fixture": fixture_name, "acceptance": True}, ensure_ascii=False),
            },
            files={"file": (fixture_name, file_obj, "text/plain")},
        )
    assert response.status_code == 201, response.text
    return response.json()


def test_e2e_acceptance_flow_covers_full_overseas_report_lifecycle(tmp_path: Path) -> None:
    """Run the complete acceptance path without real API keys or network calls."""

    enterprise = _load_json("enterprise.json")
    product = _load_json("product.json")
    generation_params = _load_json("generation_params.json")
    report_payload = json.loads(REPORT_SAMPLE_PATH.read_text(encoding="utf-8"))
    llm = MockLLM(report_payload)
    web_research = MockWebResearchService()
    knowledge_base = _make_knowledge_base_service(tmp_path)
    generation_service = OverseasPlanGenerationService(
        data_repository=InMemoryEnterpriseDataRepository(enterprises={}, products={}),
        llm_client=llm,
        knowledge_retriever=knowledge_base,
        web_research_service=web_research,
    )
    client = TestClient(create_app(generation_service=generation_service, knowledge_base_service=knowledge_base))

    enterprise_response = client.post("/api/enterprises", json=enterprise)
    assert enterprise_response.status_code == 201, enterprise_response.text
    assert enterprise_response.json()["id"] == enterprise["id"]

    product_response = client.post("/api/products", json=product)
    assert product_response.status_code == 201, product_response.text
    assert product_response.json()["enterprise_id"] == enterprise["id"]

    enterprise_file = _post_upload(
        client,
        "enterprise_profile.txt",
        enterprise_id=enterprise["id"],
        product_id=None,
        source_type="enterprise_profile",
    )
    product_file = _post_upload(
        client,
        "product_profile.txt",
        enterprise_id=enterprise["id"],
        product_id=product["id"],
        source_type="product_profile",
    )
    assert enterprise_file["parsed_status"] == "parsed"
    assert product_file["parsed_status"] == "parsed"
    assert enterprise_file["chunks"]
    assert product_file["chunks"]

    embedded_counts = []
    for file_payload in (enterprise_file, product_file):
        embed_response = client.post(f"/api/knowledge/files/{file_payload['id']}/embed")
        assert embed_response.status_code == 200, embed_response.text
        embedded_counts.append(embed_response.json()["embedded_chunk_count"])
    assert embedded_counts == [1, 1]

    search_response = client.post(
        "/api/knowledge/search",
        json={
            "query": "德国 CE 经销商 售后 SLA",
            "enterprise_id": enterprise["id"],
            "product_id": product["id"],
            "industry": "医疗器械",
            "country": "德国",
            "top_k": 3,
        },
    )
    assert search_response.status_code == 200, search_response.text
    search_results = search_response.json()["results"]
    assert search_results
    assert any("CE" in item["text"] or "经销商" in item["text"] for item in search_results)

    generate_response = client.post("/api/overseas-plans/generate", json=generation_params)
    assert generate_response.status_code == 200, generate_response.text
    generated = generate_response.json()
    project = generated["project"]
    project_id = project["id"]
    assert project["generation_status"] == "completed"
    assert generated["preview"]["report_title"] == report_payload["report_title"]
    assert len(llm.prompts) == 1
    assert len(web_research.requests) == 1
    assert "context_bundle" in llm.prompts[0][0]

    metadata = project["metadata"]
    context_bundle = metadata["context_bundle"]
    assert context_bundle["local_knowledge_context"]["chunks"]
    assert context_bundle["web_research_context"]["sources"]
    assert context_bundle["citations"]
    assert metadata["web_research"]["source_count"] == 2
    assert metadata["quality_review"]["total_score"] > 0
    assert metadata["quality_status"] in {"passed", "needs_revision", "failed_quality_check"}

    edited_result = copy.deepcopy(generated["preview"])
    edited_result["manual_acceptance_note"] = "验收人员已补充德国渠道优先级和售后 SLA 复核意见。"
    edit_response = client.post(
        f"/api/overseas-plans/{project_id}/edit",
        json={"edited_by": "acceptance-editor", "username": "验收编辑", "result": edited_result},
    )
    assert edit_response.status_code == 200, edit_response.text
    assert edit_response.json()["project"]["metadata"]["current_version_number"] == 2

    versions_response = client.get(f"/api/overseas-plans/{project_id}/versions")
    assert versions_response.status_code == 200, versions_response.text
    versions = versions_response.json()
    assert [item["version_number"] for item in versions["versions"]] == [1, 2]

    finalize_response = client.post(
        f"/api/overseas-plans/{project_id}/finalize",
        json={"version_number": 2, "finalized_by": "acceptance-owner", "username": "验收负责人"},
    )
    assert finalize_response.status_code == 200, finalize_response.text
    assert finalize_response.json()["version"]["is_final"] is True

    export_results = {}
    for export_type, expected_suffix in (("word", ".docx"), ("ppt", ".pptx"), ("excel", ".xlsx")):
        export_response = client.post(
            f"/api/overseas-plans/{project_id}/exports/{export_type}",
            json={"exported_by": "acceptance-exporter", "username": "验收导出", "report_version": "internal"},
        )
        assert export_response.status_code == 200, export_response.text
        export_payload = export_response.json()["export"]
        export_results[export_type] = export_payload
        assert export_payload["file_path"].endswith(expected_suffix)
        assert Path(export_payload["file_path"]).exists()

    audit_response = client.get(f"/api/overseas-plans/{project_id}/audit-logs")
    assert audit_response.status_code == 200, audit_response.text
    audit_actions = [item["action_type"] for item in audit_response.json()["logs"]]
    for action in (
        "create_plan",
        "ai_generate_plan",
        "edit_ai_content",
        "mark_final_version",
        "export_word",
        "export_ppt",
        "export_excel_action_plan",
    ):
        assert action in audit_actions

    final_detail_response = client.get(f"/api/overseas-plans/{project_id}", params={"viewed_by": "acceptance-reader"})
    assert final_detail_response.status_code == 200, final_detail_response.text
    final_project = final_detail_response.json()["project"]
    assert final_project["metadata"]["final_version_number"] == 2
    assert final_project["output_word"]["file_path"] == export_results["word"]["file_path"]
    assert final_project["output_ppt"]["file_path"] == export_results["ppt"]["file_path"]
    assert final_project["output_excel"]["file_path"] == export_results["excel"]["file_path"]
