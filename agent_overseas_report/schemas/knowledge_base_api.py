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


class KnowledgeFileEmbedResponse(BaseModel):
    """Response for vectorizing one parsed knowledge-base file."""

    file_id: str
    embedded_chunk_count: int
    status: str


class KnowledgeSearchRequest(BaseModel):
    """Request body for local RAG retrieval over vectorized knowledge chunks."""

    query: str = Field(..., min_length=1)
    enterprise_id: str | None = None
    product_id: str | None = None
    industry: str | None = None
    country: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class KnowledgeSearchResultResponse(BaseModel):
    """One source-preserving local RAG search result."""

    chunk_id: str
    text: str
    file_name: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None
    slide_number: int | None = None
    relevance_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """Search response wrapper that returns an empty list when nothing matches."""

    results: list[KnowledgeSearchResultResponse] = Field(default_factory=list)
