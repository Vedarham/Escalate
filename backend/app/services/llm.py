"""Multimodal LLM gateway (Groq primary, Hugging Face Inference Providers fallback).

Both providers expose an OpenAI-compatible Chat Completions API, so a single client
implementation serves both. Every call:

1. picks the vision model when images are attached, otherwise the text model;
2. asks for strict `json_schema` output, degrading to `json_object` and finally to
   prompt-only JSON if a provider/model rejects the response_format;
3. extracts + validates the JSON against the Pydantic contract, with one automatic
   "repair" round-trip if validation fails;
4. falls back to the next configured provider on rate limits / outages.

When no API key is configured (or DEMO_MODE=true) a deterministic demo response is
returned instead, so the whole platform can be demonstrated and tested offline.
"""
from __future__ import annotations

import copy
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence, TypeVar

import openai
from pydantic import BaseModel, ValidationError

from ..config import ProviderConfig, get_settings
from .images import ProcessedImage

log = logging.getLogger("llm")

M = TypeVar("M", bound=BaseModel)


class AIServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 502, details: Any = None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details


class _OutputError(Exception):
    """Model answered, but not with valid JSON for the contract."""


@dataclass
class LLMResult:
    data: Any
    mode: str
    provider: str
    model: str
    latency_ms: int
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# JSON schema helpers
# ---------------------------------------------------------------------------

_DROP_KEYS = {"title", "default", "minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems",
              "exclusiveMinimum", "exclusiveMaximum", "format"}


def strict_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema -> self-contained strict schema (refs inlined, all fields required)."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                target = copy.deepcopy(defs[node["$ref"].split("/")[-1]])
                extra = {k: v for k, v in node.items() if k != "$ref"}
                target.update(extra)
                return resolve(target)
            out = {k: resolve(v) for k, v in node.items() if k not in _DROP_KEYS}
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"].keys())
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [resolve(n) for n in node]
        return node

    return resolve(raw)


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> Any:
    if not text or not text.strip():
        raise _OutputError("empty response")
    text = _THINK_RE.sub("", text).strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise _OutputError("no JSON object found in response")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise _OutputError(f"invalid JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

_RETRYABLE_PROVIDER_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
)


class LLMGateway:
    def __init__(self) -> None:
        self._clients: dict[str, openai.OpenAI] = {}
        # remembers which response_format level each provider/model accepted
        self._format_level: dict[str, int] = {}

    # -- public -------------------------------------------------------------

    def status(self) -> dict:
        s = get_settings()
        return {
            "mode": "demo" if s.demo_mode else "live",
            "primary_provider": s.providers[0].name if s.providers else None,
            "providers": [
                {"name": p.name, "vision_model": p.vision_model, "text_model": p.text_model,
                 "fast_model": p.fast_model}
                for p in s.providers
            ],
        }

    def generate(
        self,
        *,
        system: str,
        user_text: str,
        schema: type[M],
        demo: Callable[[], M | dict],
        images: Sequence[ProcessedImage] = (),
        history: Sequence[dict] = (),
        max_tokens: int = 4096,
        fast: bool = False,
    ) -> LLMResult:
        settings = get_settings()
        t0 = time.perf_counter()
        warnings = [w for img in images for w in img.warnings]

        if settings.demo_mode:
            value = demo()
            data = value if isinstance(value, BaseModel) else schema.model_validate(value)
            return LLMResult(data, "demo", "demo", "deterministic-demo",
                             int((time.perf_counter() - t0) * 1000),
                             warnings + ["Demo mode: configure GROQ_API_KEY or HF_TOKEN for live AI analysis."])

        messages = self._build_messages(system, user_text, schema, images, history, warnings)
        failures: list[str] = []
        for provider in settings.providers:
            model = provider.vision_model if images else (provider.fast_model if fast else provider.text_model)
            try:
                data = self._call_with_repair(provider, model, messages, schema, max_tokens)
                if failures:
                    warnings.append(f"Primary provider unavailable; answered by {provider.name}.")
                return LLMResult(data, "live", provider.name, model,
                                 int((time.perf_counter() - t0) * 1000), warnings)
            except _RETRYABLE_PROVIDER_ERRORS as exc:
                log.warning("provider %s failed: %s", provider.name, exc)
                failures.append(f"{provider.name}: {type(exc).__name__}: {getattr(exc, 'message', exc)}")
            except openai.BadRequestError as exc:
                log.warning("provider %s rejected request: %s", provider.name, exc)
                failures.append(f"{provider.name}: rejected request: {getattr(exc, 'message', exc)}")
            except openai.APIStatusError as exc:  # e.g. 402 out of credits, 413, 503 variants
                log.warning("provider %s returned HTTP %s: %s", provider.name, exc.status_code, exc)
                hint = " (account has no remaining credits)" if exc.status_code == 402 else ""
                failures.append(f"{provider.name}: HTTP {exc.status_code}{hint}")
            except openai.APIError as exc:
                log.warning("provider %s API error: %s", provider.name, exc)
                failures.append(f"{provider.name}: {type(exc).__name__}")
            except _OutputError as exc:
                log.warning("provider %s produced invalid output: %s", provider.name, exc)
                failures.append(f"{provider.name}: invalid AI output: {exc}")

        if settings.fallback_to_demo:
            value = demo()
            data = value if isinstance(value, BaseModel) else schema.model_validate(value)
            return LLMResult(data, "demo", "demo-fallback", "deterministic-demo",
                             int((time.perf_counter() - t0) * 1000),
                             warnings + ["Live AI unavailable (" + "; ".join(failures) + "). Showing demo data."])

        raise AIServiceError(
            "ai_unavailable",
            "The AI service could not produce a valid response. Please retry in a moment.",
            status=502,
            details=failures,
        )

    # -- internals ----------------------------------------------------------

    def _client(self, p: ProviderConfig) -> openai.OpenAI:
        if p.name not in self._clients:
            s = get_settings()
            self._clients[p.name] = openai.OpenAI(
                api_key=p.api_key, base_url=p.base_url, timeout=s.llm_timeout,
                max_retries=3,  # SDK backs off and honours short retry-after hints on 429s
            )
        return self._clients[p.name]

    @staticmethod
    def _build_messages(system, user_text, schema, images, history, warnings) -> list[dict]:
        schema_json = json.dumps(strict_schema(schema), separators=(",", ":"))
        sys_prompt = (
            f"{system}\n\n"
            "OUTPUT RULES:\n"
            "- Reply with ONE JSON object only. No prose, no markdown fences.\n"
            "- It must validate against this JSON schema (all keys required; use \"\" or [] when unknown):\n"
            f"{schema_json}"
        )
        msgs: list[dict] = [{"role": "system", "content": sys_prompt}]
        msgs.extend({"role": m["role"], "content": m["content"]} for m in history)
        text = user_text
        if warnings:
            text += "\n\nAutomatic image quality checks: " + " ".join(warnings)
        if images:
            content: list[dict] = [{"type": "text", "text": text}]
            content += [{"type": "image_url", "image_url": {"url": img.data_url}} for img in images]
            msgs.append({"role": "user", "content": content})
        else:
            msgs.append({"role": "user", "content": text})
        return msgs

    def _response_format(self, level: int, schema: type[BaseModel]) -> dict | None:
        if level == 0:
            return {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "strict": True, "schema": strict_schema(schema)},
            }
        if level == 1:
            return {"type": "json_object"}
        return None

    def _complete(self, p: ProviderConfig, model: str, messages: list[dict], schema, max_tokens: int) -> str:
        key = f"{p.name}:{model}"
        level = self._format_level.get(key, 0)
        client = self._client(p)
        temperature = get_settings().temperature
        while True:
            kwargs: dict[str, Any] = {"model": model, "messages": messages,
                                      "temperature": temperature, "max_tokens": max_tokens}
            fmt = self._response_format(level, schema)
            if fmt:
                kwargs["response_format"] = fmt
            try:
                resp = client.chat.completions.create(**kwargs)
            except openai.BadRequestError:
                if level >= 2:
                    raise
                level += 1  # provider/model does not support this response_format - degrade
                continue
            self._format_level[key] = level
            choice = resp.choices[0]
            content = choice.message.content or ""
            if choice.finish_reason == "length" and not content.strip().endswith("}"):
                raise _OutputError("response was truncated (max tokens reached)")
            return content

    def _call_with_repair(self, p, model, messages, schema: type[M], max_tokens: int) -> M:
        content = self._complete(p, model, messages, schema, max_tokens)
        try:
            return schema.model_validate(extract_json(content))
        except (_OutputError, ValidationError) as first_error:
            log.info("repairing invalid output from %s: %s", p.name, first_error)
            repair = messages + [
                {"role": "assistant", "content": content[:6000] or "(empty)"},
                {"role": "user", "content": (
                    "Your previous reply was not valid for the required JSON schema. "
                    f"Problem: {str(first_error)[:1500]}\n"
                    "Return the corrected JSON object only."
                )},
            ]
            content = self._complete(p, model, repair, schema, max_tokens)
            try:
                return schema.model_validate(extract_json(content))
            except ValidationError as exc:
                raise _OutputError(f"schema validation failed: {exc.error_count()} errors") from exc


gateway = LLMGateway()
