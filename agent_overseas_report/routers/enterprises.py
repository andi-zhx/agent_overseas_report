"""Enterprise and product master-data API routes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from agent_overseas_report.database import EnterpriseRepository
from agent_overseas_report.schemas import (
    EnterpriseCreate,
    EnterpriseResponse,
    EnterpriseUpdate,
    ErrorResponse,
    ImportValidationIssue,
    ImportValidationRequest,
    ImportValidationResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from agent_overseas_report.services import DataNotFoundError

router = APIRouter(tags=["enterprise-master-data"])


def get_enterprise_repository(request: Request) -> EnterpriseRepository:
    """Return the app-scoped enterprise repository used by generation."""

    service = request.app.state.overseas_plan_service
    return service.data_repository


def _raise_not_found(message: str) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def _dump_model(model: BaseModel, *, exclude_unset: bool = False) -> dict[str, Any]:
    """Pydantic v2-compatible model dump helper."""

    return model.model_dump(exclude_unset=exclude_unset)


@router.get("/enterprises", response_model=list[EnterpriseResponse], summary="List enterprises")
def list_enterprises(
    offset: int = 0,
    limit: int = 100,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> list[dict[str, Any]]:
    """List structured enterprises for report parameter selection."""

    return repository.list_enterprises(offset=offset, limit=limit)


@router.post(
    "/enterprises",
    response_model=EnterpriseResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
    summary="Create enterprise",
)
def create_enterprise(
    payload: EnterpriseCreate,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> dict[str, Any]:
    """Create structured enterprise master data."""

    data = _dump_model(payload)
    data["id"] = data.get("id") or f"ent_{uuid4().hex}"
    return repository.upsert_enterprise(data)


@router.get(
    "/enterprises/{enterprise_id}",
    response_model=EnterpriseResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get enterprise",
)
def get_enterprise(
    enterprise_id: str,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> dict[str, Any]:
    """Get one enterprise by ID."""

    try:
        return repository.get_enterprise(enterprise_id)
    except DataNotFoundError:
        _raise_not_found(f"Enterprise not found: {enterprise_id}")


@router.put(
    "/enterprises/{enterprise_id}",
    response_model=EnterpriseResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Update enterprise",
)
def update_enterprise(
    enterprise_id: str,
    payload: EnterpriseUpdate,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> dict[str, Any]:
    """Partially update structured enterprise master data."""

    try:
        current = repository.get_enterprise(enterprise_id)
    except DataNotFoundError:
        _raise_not_found(f"Enterprise not found: {enterprise_id}")
    current.update(_dump_model(payload, exclude_unset=True))
    current["id"] = enterprise_id
    return repository.upsert_enterprise(current)


@router.delete(
    "/enterprises/{enterprise_id}",
    response_model=EnterpriseResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Delete enterprise",
)
def delete_enterprise(
    enterprise_id: str,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> dict[str, Any]:
    """Delete an enterprise and its products."""

    deleted = repository.delete_enterprise(enterprise_id)
    if deleted is None:
        _raise_not_found(f"Enterprise not found: {enterprise_id}")
    return deleted


@router.post("/enterprises/import/validate", response_model=ImportValidationResponse, summary="Validate enterprise import rows")
def validate_enterprise_import(payload: ImportValidationRequest) -> ImportValidationResponse:
    """Validate enterprise import fields without writing to the database."""

    return _validate_import_records(payload.records, EnterpriseCreate)


@router.get("/products", response_model=list[ProductResponse], summary="List products")
def list_products(
    enterprise_id: str | None = None,
    offset: int = 0,
    limit: int = 100,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> list[dict[str, Any]]:
    """List products, optionally scoped to one enterprise."""

    return repository.list_products(enterprise_id, offset=offset, limit=limit)


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Create product",
)
def create_product(
    payload: ProductCreate,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> dict[str, Any]:
    """Create structured product master data under one enterprise."""

    data = _dump_model(payload)
    data["id"] = data.get("id") or f"prod_{uuid4().hex}"
    try:
        return repository.upsert_product(data)
    except DataNotFoundError as exc:
        _raise_not_found(str(exc))


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get product",
)
def get_product(
    product_id: str,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> dict[str, Any]:
    """Get one product by ID."""

    products = repository.list_products(offset=0, limit=10_000)
    for product in products:
        if product["id"] == product_id:
            return product
    _raise_not_found(f"Product not found: {product_id}")


@router.put(
    "/products/{product_id}",
    response_model=ProductResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Update product",
)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> dict[str, Any]:
    """Partially update structured product master data."""

    current = get_product(product_id, repository)
    current.update(_dump_model(payload, exclude_unset=True))
    current["id"] = product_id
    try:
        return repository.upsert_product(current)
    except DataNotFoundError as exc:
        _raise_not_found(str(exc))


@router.delete(
    "/products/{product_id}",
    response_model=ProductResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Delete product",
)
def delete_product(
    product_id: str,
    repository: EnterpriseRepository = Depends(get_enterprise_repository),
) -> dict[str, Any]:
    """Delete one product."""

    deleted = repository.delete_product(product_id)
    if deleted is None:
        _raise_not_found(f"Product not found: {product_id}")
    return deleted


@router.post("/products/import/validate", response_model=ImportValidationResponse, summary="Validate product import rows")
def validate_product_import(payload: ImportValidationRequest) -> ImportValidationResponse:
    """Validate product import fields without writing to the database."""

    return _validate_import_records(payload.records, ProductCreate)


def _validate_import_records(records: list[dict[str, Any]], schema_type: type[BaseModel]) -> ImportValidationResponse:
    issues: list[ImportValidationIssue] = []
    valid_count = 0
    for index, record in enumerate(records, start=1):
        try:
            schema_type(**record)
        except ValidationError as exc:
            for error in exc.errors():
                field = ".".join(str(part) for part in error["loc"])
                issues.append(ImportValidationIssue(row=index, field=field, message=str(error["msg"])))
        else:
            valid_count += 1
    return ImportValidationResponse(valid_count=valid_count, invalid_count=len(records) - valid_count, issues=issues)
