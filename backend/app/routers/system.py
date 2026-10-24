"""Health, history and file endpoints."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from ..services import storage
from ..services.llm import gateway
from .common import AppError

router = APIRouter(tags=["System"])

Module = Literal["safety", "crack", "valuation", "planning", "daily", "chat", "legal"]


@router.get("/health")
def health():
    return {"success": True, "data": {"status": "ok", **gateway.status()}}


@router.get("/history")
def history(module: Module | None = None, limit: int = Query(30, ge=1, le=200)):
    return {"success": True, "data": {"items": storage.list_records(module, limit), "counts": storage.stats()}}


@router.get("/history/{record_id}")
def history_item(record_id: int):
    rec = storage.get_record(record_id)
    if not rec:
        raise AppError("not_found", f"Record {record_id} does not exist.", 404)
    return {"success": True, "data": rec}


@router.get("/uploads/{name}")
def uploaded_image(name: str):
    path = storage.image_path(name)
    if not path:
        raise AppError("not_found", "Image not found.", 404)
    return FileResponse(path, media_type="image/jpeg")
