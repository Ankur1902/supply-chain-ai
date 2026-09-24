"""
Standard API response envelope used by every endpoint.

Success: {"data": ..., "meta": {...}}
Error:   {"error": {"code": "...", "message": "..."}}
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    page: int | None = None
    page_size: int | None = None
    total: int | None = None
    total_pages: int | None = None
    extra: dict[str, Any] | None = None


class SuccessResponse(BaseModel, Generic[T]):
    data: T
    meta: Meta | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def success(data: Any, meta: Meta | None = None) -> dict:
    payload: dict[str, Any] = {"data": data}
    if meta is not None:
        payload["meta"] = meta.model_dump(exclude_none=True)
    return payload


def paginated(items: list[Any], page: int, page_size: int, total: int) -> dict:
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return success(
        items,
        Meta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )
