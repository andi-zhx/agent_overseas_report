"""FastAPI routes for local knowledge-base file uploads and parsing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from agent_overseas_report.knowledge_base.local_files import KnowledgeBaseService, KnowledgeFileUpload
from agent_overseas_report.schemas.knowledge_base_api import KnowledgeBaseFileResponse
from agent_overseas_report.schemas.overseas_plan_api import ErrorResponse

router = APIRouter(tags=["knowledge-base"])


def get_knowledge_base_service(request: Request) -> KnowledgeBaseService:
    """Return the app-scoped local knowledge-base service."""

    return request.app.state.knowledge_base_service


@router.post(
    "/knowledge/files/upload",
    response_model=KnowledgeBaseFileResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
    summary="Upload and parse a local knowledge file",
)
def upload_knowledge_file(
    file: Annotated[UploadFile, File(description="企业、产品或行业资料文件。")],
    enterprise_id: Annotated[str | None, Form()] = None,
    product_id: Annotated[str | None, Form()] = None,
    industry: Annotated[str | None, Form()] = None,
    country: Annotated[str | None, Form()] = None,
    source_type: Annotated[str | None, Form()] = None,
    metadata_json: Annotated[str | None, Form(description="可选 JSON 字符串形式的扩展元数据。")] = None,
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> dict[str, Any]:
    """Upload a local document, identify its type, parse text, and persist chunks."""

    metadata = _parse_metadata_json(metadata_json)
    suffix = Path(file.filename or "upload.bin").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(file.file.read())
    try:
        return service.upload_and_parse(
            KnowledgeFileUpload(
                file_name=file.filename or "upload.bin",
                temp_path=temp_path,
                content_type=file.content_type,
                enterprise_id=enterprise_id,
                product_id=product_id,
                industry=industry,
                country=country,
                source_type=source_type,
                metadata=metadata,
            )
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
        file.file.close()


@router.get("/knowledge/files", response_model=list[KnowledgeBaseFileResponse], summary="List local knowledge files")
def list_knowledge_files(
    enterprise_id: str | None = None,
    product_id: str | None = None,
    offset: int = 0,
    limit: int = 100,
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> list[dict[str, Any]]:
    """List file metadata without chunk payloads."""

    files = service.list_files(enterprise_id=enterprise_id, product_id=product_id, offset=offset, limit=limit)
    for item in files:
        item.setdefault("chunks", [])
    return files


@router.get(
    "/knowledge/files/{file_id}",
    response_model=KnowledgeBaseFileResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a local knowledge file and chunks",
)
def get_knowledge_file(
    file_id: str,
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> dict[str, Any]:
    """Get one knowledge file including parsed chunks."""

    file_payload = service.get_file(file_id)
    if file_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge file not found: {file_id}")
    return file_payload


@router.delete(
    "/knowledge/files/{file_id}",
    response_model=KnowledgeBaseFileResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a local knowledge file",
)
def delete_knowledge_file(
    file_id: str,
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> dict[str, Any]:
    """Delete file metadata, parsed chunks, and the stored local file."""

    deleted = service.delete_file(file_id)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge file not found: {file_id}")
    return deleted


def _parse_metadata_json(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        data = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="metadata_json must be valid JSON"
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="metadata_json must be a JSON object"
        )
    return data
