"""Pydantic schemas for local knowledge-base file APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeBaseChunkResponse(BaseModel):
    """Parsed text chunk response prepared for future RAG indexing."""

    id: str
    file_id: str
    chunk_index: int
    text: str
    page_number: int | None = None
    sheet_name: str | None = None
    slide_number: int | None = None
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None


class KnowledgeBaseFileResponse(BaseModel):
    """Uploaded file metadata and parser status response."""

    id: str
    file_name: str
    file_type: str
    file_path: str
    enterprise_id: str | None = None
    product_id: str | None = None
    industry: str | None = None
    country: str | None = None
    source_type: str | None = None
    uploaded_at: str
    parsed_status: str
    parse_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None
    chunks: list[KnowledgeBaseChunkResponse] = Field(default_factory=list)
