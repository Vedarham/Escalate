"""Tests for the live AI path (providers mocked): JSON extraction, repair, format
degradation, provider fallback, normalisation and schedule verification."""
import dataclasses
import json
from types import SimpleNamespace

import openai
import pytest

try:  # the openai SDK builds its errors on httpx2 (newer) or httpx (older)
    import httpx2 as _httpx
except ImportError:  # pragma: no cover
    import httpx as _httpx

from app.config import ProviderConfig, get_settings
from app.schemas import AITask, CrackReport, SafetyReport, ValuationReport
from app.services import demo
from app.services import llm as llm_mod
from app.services.estimator import compute_schedule
from app.services.llm import AIServiceError, LLMGateway, extract_json, strict_schema


def _resp(content, finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)])


def _err(cls, status):
    r = _httpx.Response(status, request=_httpx.Request("POST", "https://example.test/v1/chat/completions"))
    return cls("boom", response=r, body=None)


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return _resp(out)


@pytest.fixture
def live(monkeypatch):
    """Gateway configured with two fake providers (groq primary, huggingface fallback)."""
    settings = dataclasses.replace(
        get_settings(), force_demo=False, llm_provider="groq",
        groq=ProviderConfig("groq", "k1", "https://groq.test", "vision-g", "text-g", "fast-g"),
        huggingface=ProviderConfig("huggingface", "k2", "https://hf.test", "vision-h", "text-h", "fast-h"),
    )
    monkeypatch.setattr(llm_mod, "get_settings", lambda: settings)
    gw = LLMGateway()
    clients = {}

    def install(groq_outputs, hf_outputs=()):
        clients["groq"] = FakeClient(groq_outputs)
        clients["huggingface"] = FakeClient(hf_outputs)
        monkeypatch.setattr(gw, "_client", lambda p: clients[p.name])
        return clients

    return gw, install


SAFETY_JSON = json.dumps(demo.safety_demo())


def _gen(gw, schema=SafetyReport):
    return gw.generate(system="sys", user_text="analyse", schema=schema, demo=lambda: {})


def test_live_success_uses_strict_schema(live):
    gw, install = live
    clients = install([SAFETY_JSON])
    res = _gen(gw)
    assert res.mode == "live" and res.provider == "groq" and res.model == "text-g"
    fmt = clients["groq"].calls[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True


def test_think_tags_and_fences_are_stripped(live):
    gw, install = live
    install([f"<think>reasoning...</think>\n```json\n{SAFETY_JSON}\n```"])
    assert isinstance(_gen(gw).data, SafetyReport)


def test_invalid_output_is_repaired(live):
    gw, install = live
    clients = install(['{"scene_summary": "only one field"}', SAFETY_JSON])
    res = _gen(gw)
    assert res.data.scene_summary
    assert "not valid" in clients["groq"].calls[1]["messages"][-1]["content"]


def test_response_format_degrades_when_unsupported(live):
    gw, install = live
    clients = install([_err(openai.BadRequestError, 400), SAFETY_JSON])
    _gen(gw)
    assert clients["groq"].calls[0]["response_format"]["type"] == "json_schema"
    assert clients["groq"].calls[1]["response_format"] == {"type": "json_object"}


def test_fallback_to_second_provider(live):
    gw, install = live
    install([_err(openai.RateLimitError, 429)], [SAFETY_JSON])
    res = _gen(gw)
    assert res.provider == "huggingface"
    assert any("fallback" in w.lower() or "answered by" in w for w in res.warnings)


def test_all_providers_fail(live):
    gw, install = live
    install([_err(openai.InternalServerError, 500)], ["no json here", "still not json"])
    with pytest.raises(AIServiceError) as exc:
        _gen(gw)
    assert exc.value.code == "ai_unavailable" and len(exc.value.details) == 2


def test_out_of_credits_falls_back(live):
    gw, install = live
    install([_err(openai.APIStatusError, 402)], [SAFETY_JSON])
    assert _gen(gw).provider == "huggingface"


def test_out_of_credits_everywhere_reports_cleanly(live):
    gw, install = live
    install([_err(openai.APIStatusError, 402)], [_err(openai.APIStatusError, 402)])
    with pytest.raises(AIServiceError) as exc:
        _gen(gw)
    assert all("no remaining credits" in d for d in exc.value.details)


def test_optional_demo_fallback(live, monkeypatch):
    gw, install = live
    settings = dataclasses.replace(llm_mod.get_settings(), fallback_to_demo=True)
    monkeypatch.setattr(llm_mod, "get_settings", lambda: settings)
    install([_err(openai.RateLimitError, 429)], [_err(openai.RateLimitError, 429)])
    res = gw.generate(system="s", user_text="u", schema=SafetyReport, demo=demo.safety_demo)
    assert res.mode == "demo" and res.provider == "demo-fallback"
    assert any("Live AI unavailable" in w for w in res.warnings)


def test_vision_model_selected_for_images(live):
    from app.services.images import process_image
    from tests.conftest import make_image
    gw, install = live
    clients = install([SAFETY_JSON])
    img = process_image(make_image())
    res = gw.generate(system="s", user_text="u", schema=SafetyReport, demo=lambda: {}, images=[img])
    assert res.model == "vision-g"
    content = clients["groq"].calls[0]["messages"][-1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_live_ai_error_maps_to_502(client, monkeypatch, jpeg):
    def boom(**_):
        raise AIServiceError("ai_unavailable", "down", details=["x"])
    monkeypatch.setattr(llm_mod.gateway, "generate", boom)
    r = client.post("/api/safety/analyze", files={"image": ("s.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_unavailable"


# --------------------------------------------------------------------------- contracts

def test_strict_schema_is_self_contained():
    s = json.dumps(strict_schema(CrackReport))
    assert "$ref" not in s and "$defs" not in s
    schema = strict_schema(CrackReport)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_normalisation_of_messy_model_output():
    raw = demo.safety_demo()
    raw.update(overall_risk_level="HIGH", safety_score=140, confidence=85, positive_observations="one item")
    raw["hazards"][0]["severity"] = "Critical"
    rep = SafetyReport.model_validate(raw)
    assert rep.overall_risk_level == "high" and rep.safety_score == 100
    assert rep.confidence == 0.85 and rep.positive_observations == ["one item"]
    assert rep.hazards[0].severity == "critical"


def test_value_range_is_ordered():
    from app.schemas import ValuationInput
    raw = demo.valuation_demo(ValuationInput(location="Pune", property_type="villa", built_up_area_sqft=2000), False)
    raw["estimated_value"] = {"low": 300, "mid": 100, "high": 200}
    ev = ValuationReport.model_validate(raw).estimated_value
    assert (ev.low, ev.mid, ev.high) == (100, 200, 300)


def test_extract_json_errors():
    with pytest.raises(Exception):
        extract_json("")
    with pytest.raises(Exception):
        extract_json("sorry, I cannot help")
    assert extract_json('prefix {"a": 1} suffix') == {"a": 1}


# --------------------------------------------------------------------------- schedule verification

def _t(i, dur, deps):
    return AITask(id=i, task=f"task {i}", phase="p", duration_days=dur, depends_on=deps, resources="")


def test_schedule_cpm():
    tasks = [_t("A", 5, []), _t("B", 3, ["A"]), _t("C", 10, ["A"]), _t("D", 2, ["B", "C"])]
    sched, total, path, warns = compute_schedule(tasks)
    assert total == 17 and path == ["A", "C", "D"] and not warns
    b = next(t for t in sched if t.id == "B")
    assert not b.critical and b.start_day == 5


def test_schedule_repairs_bad_ai_graph():
    tasks = [_t("A", 4, ["C"]), _t("B", 2, ["A", "ZZZ"]), _t("C", 3, ["B"]), _t("A", 1, [])]
    sched, total, path, warns = compute_schedule(tasks)
    assert len(sched) == 4 and total > 0
    assert any("cycle" in w for w in warns) and any("invalid" in w for w in warns)
    assert any("Duplicate" in w for w in warns)
