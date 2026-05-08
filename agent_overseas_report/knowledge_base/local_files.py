"""Persistence and orchestration for uploaded local knowledge files."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from agent_overseas_report.database.models import KnowledgeBaseChunkORM, KnowledgeBaseFileORM
from agent_overseas_report.knowledge_base.parsers import (
    estimate_token_count,
    identify_file_type,
    parse_document,
    split_text_blocks,
)


@dataclass(slots=True)
class KnowledgeFileUpload:
    """Input metadata and temporary file path for a knowledge-base upload."""

    file_name: str
    temp_path: Path
    content_type: str | None = None
    enterprise_id: str | None = None
    product_id: str | None = None
    industry: str | None = None
    country: str | None = None
    source_type: str | None = None
    metadata: dict[str, Any] | None = None


class KnowledgeFileNotFoundError(LookupError):
    """Raised when a knowledge file cannot be found."""


class SQLAlchemyKnowledgeBaseRepository:
    """SQLite/SQLAlchemy repository for local knowledge-file metadata and chunks."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def create_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        row = KnowledgeBaseFileORM(
            id=payload["id"],
            created_at=now,
            updated_at=now,
            status="active",
            metadata_=payload.get("metadata", {}),
            file_name=payload["file_name"],
            file_type=payload["file_type"],
            file_path=payload["file_path"],
            enterprise_id=payload.get("enterprise_id"),
            product_id=payload.get("product_id"),
            industry=payload.get("industry"),
            country=payload.get("country"),
            source_type=payload.get("source_type"),
            uploaded_at=payload.get("uploaded_at") or now,
            parsed_status=payload.get("parsed_status", "pending"),
            parse_error=payload.get("parse_error"),
        )
        with self.session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return _file_row_to_payload(row, include_chunks=True)

    def replace_parse_result(
        self, file_id: str, chunks: list[dict[str, Any]], *, parse_error: str | None = None
    ) -> dict[str, Any]:
        status = "failed" if parse_error else "parsed"
        with self.session_factory() as session:
            row = session.get(KnowledgeBaseFileORM, file_id)
            if row is None:
                raise KnowledgeFileNotFoundError(file_id)
            session.execute(delete(KnowledgeBaseChunkORM).where(KnowledgeBaseChunkORM.file_id == file_id))
            now = datetime.now(timezone.utc)
            for chunk in chunks:
                session.add(
                    KnowledgeBaseChunkORM(
                        id=chunk.get("id") or f"kbc_{uuid4().hex}",
                        created_at=now,
                        updated_at=now,
                        status="active",
                        metadata_=chunk.get("metadata", {}),
                        file_id=file_id,
                        chunk_index=chunk["chunk_index"],
                        text=chunk["text"],
                        page_number=chunk.get("page_number"),
                        sheet_name=chunk.get("sheet_name"),
                        slide_number=chunk.get("slide_number"),
                        token_count=chunk.get("token_count", 0),
                    )
                )
            row.updated_at = now
            row.parsed_status = status
            row.parse_error = parse_error
            session.commit()
            session.refresh(row)
            return _file_row_to_payload(row, include_chunks=True)

    def list_files(
        self, *, enterprise_id: str | None = None, product_id: str | None = None, offset: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]:
        stmt = (
            select(KnowledgeBaseFileORM)
            .order_by(KnowledgeBaseFileORM.uploaded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if enterprise_id:
            stmt = stmt.where(KnowledgeBaseFileORM.enterprise_id == enterprise_id)
        if product_id:
            stmt = stmt.where(KnowledgeBaseFileORM.product_id == product_id)
        with self.session_factory() as session:
            rows = session.scalars(stmt).all()
            return [_file_row_to_payload(row, include_chunks=False) for row in rows]

    def get_file(self, file_id: str, *, include_chunks: bool = True) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(KnowledgeBaseFileORM, file_id)
            if row is None:
                return None
            return _file_row_to_payload(row, include_chunks=include_chunks)

    def delete_file(self, file_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(KnowledgeBaseFileORM, file_id)
            if row is None:
                return None
            payload = _file_row_to_payload(row, include_chunks=True)
            session.delete(row)
            session.commit()
            return payload


class KnowledgeBaseService:
    """Application service for storing uploads and extracting text chunks."""

    def __init__(self, repository: SQLAlchemyKnowledgeBaseRepository, storage_dir: Path | str) -> None:
        self.repository = repository
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def upload_and_parse(self, upload: KnowledgeFileUpload) -> dict[str, Any]:
        file_id = f"kbf_{uuid4().hex}"
        file_type = identify_file_type(upload.file_name, upload.content_type)
        destination = self.storage_dir / file_id / upload.file_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(upload.temp_path, destination)
        payload = self.repository.create_file(
            {
                "id": file_id,
                "file_name": upload.file_name,
                "file_type": file_type,
                "file_path": str(destination),
                "enterprise_id": upload.enterprise_id,
                "product_id": upload.product_id,
                "industry": upload.industry,
                "country": upload.country,
                "source_type": upload.source_type,
                "uploaded_at": datetime.now(timezone.utc),
                "parsed_status": "pending",
                "metadata": upload.metadata or {},
            }
        )
        try:
            parsed_blocks = parse_document(destination, file_type)
            chunks = [
                {
                    "chunk_index": index,
                    "text": block.text,
                    "page_number": block.page_number,
                    "sheet_name": block.sheet_name,
                    "slide_number": block.slide_number,
                    "token_count": estimate_token_count(block.text),
                    "metadata": block.metadata,
                }
                for index, block in enumerate(split_text_blocks(parsed_blocks))
            ]
            return self.repository.replace_parse_result(file_id, chunks)
        except Exception as exc:
            return self.repository.replace_parse_result(file_id, [], parse_error=str(exc))

    def list_files(
        self, *, enterprise_id: str | None = None, product_id: str | None = None, offset: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]:
        return self.repository.list_files(
            enterprise_id=enterprise_id, product_id=product_id, offset=offset, limit=limit
        )

    def get_file(self, file_id: str) -> dict[str, Any] | None:
        return self.repository.get_file(file_id, include_chunks=True)

    def delete_file(self, file_id: str, *, remove_physical_file: bool = True) -> dict[str, Any] | None:
        deleted = self.repository.delete_file(file_id)
        if deleted and remove_physical_file:
            file_path = Path(deleted["file_path"])
            if file_path.exists():
                file_path.unlink()
            if file_path.parent.exists() and not any(file_path.parent.iterdir()):
                file_path.parent.rmdir()
        return deleted


def _file_row_to_payload(row: KnowledgeBaseFileORM, *, include_chunks: bool) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "file_name": row.file_name,
        "file_type": row.file_type,
        "file_path": row.file_path,
        "enterprise_id": row.enterprise_id,
        "product_id": row.product_id,
        "industry": row.industry,
        "country": row.country,
        "source_type": row.source_type,
        "uploaded_at": _dt(row.uploaded_at),
        "parsed_status": row.parsed_status,
        "parse_error": row.parse_error,
        "metadata": row.metadata_ or {},
        "status": row.status,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }
    if include_chunks:
        payload["chunks"] = [_chunk_row_to_payload(chunk) for chunk in row.chunks]
    return payload


def _chunk_row_to_payload(row: KnowledgeBaseChunkORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "file_id": row.file_id,
        "chunk_index": row.chunk_index,
        "text": row.text,
        "page_number": row.page_number,
        "sheet_name": row.sheet_name,
        "slide_number": row.slide_number,
        "token_count": row.token_count,
        "metadata": row.metadata_ or {},
        "status": row.status,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _dt(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else value
