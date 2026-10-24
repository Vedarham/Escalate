"""Application settings loaded from environment variables / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _storage_dir() -> Path:
    """SQLite + uploads location. Serverless hosts (Vercel) only allow writes to /tmp."""
    configured = os.getenv("STORAGE_DIR", "").strip()
    if os.getenv("VERCEL"):  # read-only bundle: always write under /tmp
        return Path(configured) if configured.startswith("/tmp/") else Path("/tmp/escalate-storage")
    return (BACKEND_DIR / (configured or "storage")).resolve()


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    vision_model: str
    text_model: str
    fast_model: str  # light model for simple steps (e.g. agent planning); own rate-limit bucket


@dataclass(frozen=True)
class Settings:
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "groq").strip().lower())
    groq: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(
            name="groq",
            api_key=os.getenv("GROQ_API_KEY", "").strip(),
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            vision_model=os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b"),
            text_model=os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-120b"),
            fast_model=os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b"),
        )
    )
    huggingface: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(
            name="huggingface",
            api_key=os.getenv("HF_TOKEN", "").strip(),
            base_url=os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1"),
            vision_model=os.getenv("HF_VISION_MODEL", "Qwen/Qwen3.8-27B"),
            text_model=os.getenv("HF_TEXT_MODEL", "Qwen/Qwen3.8-27B"),
            fast_model=os.getenv("HF_FAST_MODEL", os.getenv("HF_TEXT_MODEL", "Qwen/Qwen3.8-27B")),
        )
    )
    force_demo: bool = field(default_factory=lambda: _bool("DEMO_MODE"))
    fallback_to_demo: bool = field(default_factory=lambda: _bool("FALLBACK_TO_DEMO"))
    max_image_mb: float = field(default_factory=lambda: float(os.getenv("MAX_IMAGE_MB", "8")))
    llm_timeout: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "90")))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.2")))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        )
    )
    storage_dir: Path = field(default_factory=lambda: _storage_dir())

    @property
    def providers(self) -> list[ProviderConfig]:
        """Configured providers (with a key), primary first."""
        ordered = [self.groq, self.huggingface]
        if self.llm_provider == "huggingface":
            ordered.reverse()
        return [p for p in ordered if p.api_key]

    @property
    def demo_mode(self) -> bool:
        return self.force_demo or not self.providers


@lru_cache
def get_settings() -> Settings:
    return Settings()
