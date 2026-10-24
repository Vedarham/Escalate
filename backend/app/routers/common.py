"""Shared helpers for routers: errors, payload parsing, image intake, response envelope."""
from __future__ import annotations

from typing import Any, TypeVar

from fastapi import UploadFile
from pydantic import BaseModel, ValidationError

from ..config import get_settings
from ..schemas import Meta
from ..services import storage
from ..services.images import ImageValidationError, ProcessedImage, process_image
from ..services.llm import LLMResult

P = TypeVar("P", bound=BaseModel)


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: Any = None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details


def parse_payload(raw: str | None, model: type[P]) -> P:
    if raw is None or not raw.strip():
        raise AppError("missing_payload", "The 'payload' form field (JSON) is required.", 422)
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        raise AppError("invalid_payload", "Some fields are missing or invalid.", 422,
                       [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()])


def read_image(upload: UploadFile | None, required: bool) -> ProcessedImage | None:
    if upload is None or not upload.filename:
        if required:
            raise AppError("image_required", "Please upload an image for this analysis.", 422)
        return None
    raw = upload.file.read()
    try:
        return process_image(raw, upload.filename, get_settings().max_image_mb)
    except ImageValidationError as exc:
        status = 413 if exc.code == "image_too_large" else 422
        raise AppError(exc.code, exc.message, status)


def envelope(module: str, title: str, inputs: dict, data: BaseModel, result: LLMResult,
             image: ProcessedImage | None = None, extra_warnings: list[str] | None = None) -> dict:
    warnings = list(dict.fromkeys(result.warnings + (extra_warnings or [])))
    image_file = storage.save_image(image.jpeg_bytes) if image else None
    payload = data.model_dump(mode="json")
    record_id = storage.record(module, title, inputs, payload, result.mode, result.provider, image_file)
    meta = Meta(mode=result.mode, provider=result.provider, model=result.model,
                latency_ms=result.latency_ms, warnings=warnings, record_id=record_id)
    return {"success": True, "data": payload, "meta": meta.model_dump()}
