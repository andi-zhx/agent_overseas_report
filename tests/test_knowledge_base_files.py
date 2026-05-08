from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from agent_overseas_report.database import create_session_factory, initialize_database
from agent_overseas_report.knowledge_base.local_files import KnowledgeBaseService, KnowledgeFileUpload, SQLAlchemyKnowledgeBaseRepository
from agent_overseas_report.knowledge_base.parsers import identify_file_type


def make_service(tmp_path: Path) -> KnowledgeBaseService:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    initialize_database(engine)
    return KnowledgeBaseService(SQLAlchemyKnowledgeBaseRepository(create_session_factory(engine)), tmp_path / "uploads")


def test_identify_file_type_from_common_extensions() -> None:
    assert identify_file_type("company.pdf") == "pdf"
    assert identify_file_type("product.docx") == "word"
    assert identify_file_type("market.xlsx") == "excel"
    assert identify_file_type("slides.pptx") == "ppt"
    assert identify_file_type("notes.md") == "markdown"
    assert identify_file_type("notes.txt") == "txt"


def test_txt_upload_is_parsed_and_stored_as_chunks(tmp_path: Path) -> None:
    source = tmp_path / "enterprise.txt"
    source.write_text("企业介绍\n核心产品：智能传感器\n目标国家：德国", encoding="utf-8")
    service = make_service(tmp_path)

    uploaded = service.upload_and_parse(
        KnowledgeFileUpload(
            file_name="enterprise.txt",
            temp_path=source,
            enterprise_id="ent-1",
            product_id="prod-1",
            industry="工业设备",
            country="德国",
            source_type="enterprise_profile",
            metadata={"department": "marketing"},
        )
    )

    assert uploaded["file_type"] == "txt"
    assert uploaded["enterprise_id"] == "ent-1"
    assert uploaded["parsed_status"] == "parsed"
    assert uploaded["parse_error"] is None
    assert len(uploaded["chunks"]) == 1
    assert "智能传感器" in uploaded["chunks"][0]["text"]
    assert uploaded["chunks"][0]["token_count"] > 0
    assert service.get_file(uploaded["id"])["chunks"][0]["metadata"]["encoding"] == "utf-8"


def test_parse_failure_is_recorded_without_chunks(tmp_path: Path) -> None:
    source = tmp_path / "unknown.bin"
    source.write_bytes(b"not supported")
    service = make_service(tmp_path)

    uploaded = service.upload_and_parse(KnowledgeFileUpload(file_name="unknown.bin", temp_path=source))

    assert uploaded["file_type"] == "unknown"
    assert uploaded["parsed_status"] == "failed"
    assert "Unsupported file type" in uploaded["parse_error"]
    assert uploaded["chunks"] == []
