"""Land legal advisory agent: knowledge-base integrity, retrieval quality (RAG eval),
citation verification and API edge cases."""
import json
import re

import pytest

from app.schemas import LegalAdvice, LegalAnswerAI
from app.services import legal_agent
from app.services.legal_kb import JURISDICTIONS, get_index, parse_kb, tokenize
from app.services.llm import LLMResult

# --------------------------------------------------------------------------- knowledge base


def test_kb_integrity():
    arts = parse_kb()
    assert len(arts) >= 50
    ids = [a.id for a in arts]
    assert len(ids) == len(set(ids)), "duplicate article ids"
    for a in arts:
        assert re.fullmatch(r"[A-Z]{2}(?:-[A-Z]{2,3})*-\d{2}", a.id), a.id
        assert a.title and len(a.body) > 150, a.id
        assert a.sources, f"{a.id} must cite its sources"
        assert all(j in JURISDICTIONS for j in a.jurisdictions), a.id


def test_tokenizer_handles_legal_terms():
    toks = tokenize("Satbara (7/12) and EC for a GPA sale")
    for t in ("7/12", "encumbrance", "certificate", "power", "attorney"):
        assert t in toks


# Retrieval evaluation set: question -> article that must be in the top 5
RAG_EVAL = [
    ("The 7/12 extract shows a different name than the seller", "maharashtra", "ST-MH-01"),
    ("Seller is selling through a GPA holder, is it safe?", None, "TX-04"),
    ("Can an NRI buy farmland in India?", None, "LR-07"),
    ("My father's sister was not included when grandfather's land was divided", None, "FS-02"),
    ("someone has been living on my plot for 15 years", None, "DF-04"),
    ("Is EC enough to know there is no loan on the property?", None, "TT-06"),
    ("builder delayed possession by 2 years what can I do", None, "TX-09"),
    ("I am not a farmer, can I buy agricultural land in Maharashtra", "maharashtra", "LR-01"),
    ("plot is in B khata layout in Bangalore", "karnataka", "ST-KA-01"),
    ("seller took advance and now refuses to register the sale deed", None, "TX-03"),
    ("one of the co-owners refuses to sign", None, "TX-10"),
    ("how much TDS to deduct when buying a house for 80 lakh", None, "TX-07"),
    ("is a minor's share sale valid without court order", None, "FS-04"),
    ("the plot does not have a road access", None, "DF-06"),
    ("what documents should I check before buying a plot", None, "DD-01"),
    ("flat has no occupancy certificate", None, "DD-02"),
    ("land is in lal dora area of delhi village", "delhi", "ST-DL-01"),
    ("mutation done in my name so am I the owner?", None, "TT-05"),
    ("patta and chitta do not match the sale deed", "tamil-nadu", "ST-TN-01"),
    ("the land is marked as gairan government land", None, "LR-03"),
    ("property is under a pending court case", None, "TX-05"),
    ("is new tenure land in Gujarat transferable", "gujarat", "ST-GJ-01"),
    ("khasra and B-1 show a different owner in Indore", "madhya-pradesh", "ST-MP-01"),
    ("can a non-tribal buy tribal land in Madhya Pradesh", "madhya-pradesh", "ST-MP-02"),
    ("diversion of agricultural land for a house in Bhopal", "madhya-pradesh", "ST-MP-02"),
]


@pytest.mark.parametrize("question,state,expected", RAG_EVAL)
def test_retrieval_recall_at_5(question, state, expected):
    ids = [h.article.id for h in get_index().search([question], state, k=5)]
    assert expected in ids, f"{expected} not in {ids}"


def test_jurisdiction_boost_prefers_state_article():
    ix = get_index()
    q = ["record of rights extract mutation entries"]
    assert ix.search(q, "maharashtra", k=3)[0].article.id.startswith("ST-MH")
    assert ix.search(q, "karnataka", k=3)[0].article.id.startswith("ST-KA")


def test_off_topic_query_retrieves_little():
    assert get_index().search(["who will win the cricket world cup"], None, k=6) == []


# --------------------------------------------------------------------------- agent (demo mode)


def _ask(client, content, **profile):
    payload = {"messages": [{"role": "user", "content": content}], **profile}
    return client.post("/api/legal/ask", data={"payload": json.dumps(payload)})


def test_agent_contract_and_grounding(client):
    r = _ask(client, "Is it safe to buy a plot from a power of attorney holder?",
             jurisdiction="maharashtra", property_type="residential_plot")
    assert r.status_code == 200, r.text
    body = r.json()
    adv = LegalAdvice.model_validate(body["data"])
    assert "TX-04" in adv.citations
    retrieved = {s.id for s in adv.sources}
    assert set(adv.citations) <= retrieved, "every citation must be a retrieved passage"
    assert all(s.cited == (s.id in adv.citations) for s in adv.sources)
    assert adv.knowledge_base_articles >= 50 and adv.disclaimer
    assert body["meta"]["record_id"]


def test_agent_with_document_photo(client, jpeg):
    payload = {"messages": [{"role": "user", "content": "Please check this 7/12 extract"}], "jurisdiction": "maharashtra"}
    r = client.post("/api/legal/ask", data={"payload": json.dumps(payload)},
                    files={"image": ("712.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 200 and r.json()["data"]["sources"]


def test_agent_multi_turn(client):
    msgs = [{"role": "user", "content": "I want to buy farmland"},
            {"role": "assistant", "content": "Which state is the land in?"},
            {"role": "user", "content": "Gujarat, and I am not a farmer"}]
    r = client.post("/api/legal/ask", data={"payload": json.dumps({"messages": msgs})})
    assert r.status_code == 200


@pytest.mark.parametrize("payload", [
    {"messages": []},
    {"messages": [{"role": "assistant", "content": "hi"}]},
    {"messages": [{"role": "user", "content": "x"}], "jurisdiction": "atlantis"},
    {"messages": [{"role": "user", "content": "x"}], "buyer_profile": "alien"},
    {"messages": [{"role": "user", "content": "x"}], "extra": 1},
])
def test_agent_invalid_payloads(client, payload):
    r = client.post("/api/legal/ask", data={"payload": json.dumps(payload)})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_payload"


def test_kb_endpoints(client):
    data = client.get("/api/legal/kb").json()["data"]
    assert len(data["articles"]) >= 50 and "maharashtra" in data["jurisdictions"]
    art = client.get("/api/legal/kb/TX-04").json()["data"]
    assert "Suraj Lamp" in art["sources"]
    assert client.get("/api/legal/kb/ZZ-99").status_code == 404


def test_history_filter_includes_legal(client):
    _ask(client, "What is an encumbrance certificate?")
    items = client.get("/api/history", params={"module": "legal"}).json()["data"]["items"]
    assert items and all(i["module"] == "legal" for i in items)


# --------------------------------------------------------------------------- citation verifier (live path mocked)


def _fake_answer(citations, text):
    return {"in_scope": True, "summary": f"Short answer {text}", "detailed_answer": f"Details {text}",
            "risk_level": "high", "red_flags": [], "documents_to_verify": [], "next_steps": [],
            "applicable_laws": [], "citations": citations, "clarifying_questions": [],
            "when_to_consult_lawyer": "Now.", "confidence": 0.9}


def _patch_gateway(monkeypatch, answer):
    calls = []

    def fake_generate(**kw):
        calls.append(kw)
        if kw["schema"].__name__ == "LegalPlan":
            data = kw["schema"].model_validate({"jurisdiction": "maharashtra", "issue_categories": ["title"],
                                                "search_queries": ["power of attorney sale"],
                                                "needs_clarification": True,
                                                "clarifying_questions": ["How did the seller acquire it?"]})
        else:
            data = LegalAnswerAI.model_validate(answer)
        return LLMResult(data, "live", "groq", "m", 5, [])

    monkeypatch.setattr(legal_agent.gateway, "generate", fake_generate)
    return calls


def test_fabricated_citations_are_removed(monkeypatch, client):
    calls = _patch_gateway(monkeypatch, _fake_answer(["TX-04", "ZZ-99"], "see [TX-04] and [QQ-01]"))
    body = _ask(client, "Buying via GPA holder - safe?").json()
    d = body["data"]
    assert d["citations"] == ["TX-04"]
    assert "[QQ-01]" not in d["detailed_answer"] and "[TX-04]" in d["detailed_answer"]
    assert any("not retrieved" in w for w in body["meta"]["warnings"])
    assert "How did the seller acquire it?" in d["clarifying_questions"]
    # planner used the fast model tier; answer step received the retrieved passages
    assert calls[0].get("fast") is True and "[TX-04]" in calls[1]["user_text"]


def test_missing_citations_fall_back_to_top_passages(monkeypatch, client):
    _patch_gateway(monkeypatch, _fake_answer([], "no cites"))
    d = _ask(client, "Buying via GPA holder - safe?").json()["data"]
    assert d["citations"] and set(d["citations"]) <= {s["id"] for s in d["sources"]}
