"""FastAPI entry point for Escalate, the AI-powered multimodal construction intelligence platform."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .routers import analysis, assistant, legal, planning, system
from .routers.common import AppError
from .services.llm import AIServiceError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

settings = get_settings()
app = FastAPI(
    title="Escalate API",
    version="1.0.0",
    description="Multimodal AI decision support for construction safety, crack analysis, valuation, "
                "planning, daily site advisory, knowledge assistance and land-purchase legal guidance. All responses follow strict JSON contracts.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"success": False, "error": {"code": code, "message": message, "details": details}})


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return _error(exc.status, exc.code, exc.message, exc.details)


@app.exception_handler(AIServiceError)
async def ai_error_handler(_: Request, exc: AIServiceError):
    log.error("AI service error: %s | %s", exc.message, exc.details)
    return _error(exc.status, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
    return _error(422, "invalid_input", "Some fields are missing or invalid.", details)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException):
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return _error(500, "internal_error", "Unexpected server error. Please try again.")


for r in (system.router, analysis.router, planning.router, assistant.router, legal.router):
    app.include_router(r, prefix="/api")


@app.get("/")
@app.get("/api")
def root_info():
    return {
        "success": True,
        "data": {
            "name": "Escalate API",
            "version": "1.0.0",
            "status": "healthy",
            "health_endpoint": "/api/health",
        },
    }


# Serve the built React app (frontend/dist) when present. API routes always take priority;
# on Vercel the files are promoted to the CDN automatically, locally FastAPI serves them.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.is_dir() and not os.getenv("VERCEL"):
    if hasattr(app, "frontend"):
        app.frontend("/", directory=DIST, fallback="index.html")
    else:
        from starlette.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
