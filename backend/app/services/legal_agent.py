"""Land-purchase legal advisory agent: plan -> retrieve (BM25 RAG) -> answer -> verify citations.

Step 1  Planner (LLM, text model): infers jurisdiction and issues, writes search queries.
Step 2  Retriever (local BM25 over the curated land-law knowledge base), state-aware.
Step 3  Answerer (LLM; vision model when a document photo is attached) writes a grounded
        answer that must cite passage IDs.
Step 4  Verifier (code): drops citations to passages that were not retrieved, strips
        fabricated [IDs] from the text, and adjusts confidence when retrieval was weak.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import prompts
from ..schemas import LegalAdvice, LegalAnswerAI, LegalInput, LegalPlan, LegalSource
from .images import ProcessedImage
from .legal_kb import JURISDICTIONS, Hit, get_index
from .llm import LLMResult, gateway

DISCLAIMER = ("General legal information based on a curated knowledge base, not legal advice. Laws, rates and "
              "procedures change and vary by state; have a property advocate verify title before you pay.")
_CITE_RE = re.compile(r"\[([A-Z]{2}(?:-[A-Z]{2,3})*-\d{2})\]")
PROPERTY_LABEL = {"agricultural_land": "agricultural land", "residential_plot": "residential plot",
                  "apartment": "apartment / flat", "house": "independent house", "commercial": "commercial property",
                  "industrial": "industrial plot", "unknown": "not specified"}
BUYER_LABEL = {"resident_indian": "resident Indian", "nri": "NRI", "oci": "OCI cardholder",
               "foreign_national": "foreign national", "company": "company / firm", "unknown": "not specified"}


@dataclass
class AgentRun:
    advice: LegalAdvice
    mode: str
    provider: str
    model: str
    latency_ms: int
    warnings: list[str] = field(default_factory=list)


def _profile_text(inp: LegalInput) -> str:
    state = JURISDICTIONS.get(inp.jurisdiction, inp.jurisdiction or "not specified")
    return (f"Buyer profile: state = {state}; property type = {PROPERTY_LABEL[inp.property_type]}; "
            f"buyer = {BUYER_LABEL[inp.buyer_profile]}.")


def _history(inp: LegalInput) -> list[dict]:
    return [m.model_dump() for m in inp.messages[:-1]][-6:]


# ---------------------------------------------------------------------------
# demo-mode (offline) planner and answerer - retrieval stays real
# ---------------------------------------------------------------------------

def _demo_plan(inp: LegalInput) -> dict:
    q = inp.messages[-1].content
    extra = PROPERTY_LABEL[inp.property_type] if inp.property_type != "unknown" else ""
    return {"jurisdiction": inp.jurisdiction or "unknown", "issue_categories": [],
            "search_queries": [q, f"{q} {extra}".strip()], "needs_clarification": False,
            "clarifying_questions": []}


def _first_sentence(text: str) -> str:
    m = re.search(r"(.+?[.!?])(\s|$)", text.replace("\n", " "))
    return (m.group(1) if m else text[:200]).strip()


def _demo_answer(hits: list[Hit]) -> dict:
    if not hits:
        return {"in_scope": False, "summary": "[Demo mode] No relevant land-law articles were found for this question.",
                "detailed_answer": "Try rephrasing with terms such as title, sale deed, 7/12, inheritance, or power of attorney.",
                "risk_level": "low", "red_flags": [], "documents_to_verify": [], "next_steps": [],
                "applicable_laws": [], "citations": [], "clarifying_questions": [],
                "when_to_consult_lawyer": "Consult a property lawyer for transaction-specific advice.", "confidence": 0.1}
    top = hits[:3]
    detailed = "\n\n".join(f"**{h.article.title}** [{h.article.id}]\n{h.article.excerpt(600)}" for h in top)
    return {
        "in_scope": True,
        "summary": f"[Demo mode] {_first_sentence(top[0].article.body)} [{top[0].article.id}]",
        "detailed_answer": detailed,
        "risk_level": "medium",
        "red_flags": [{"issue": h.article.title, "why_it_matters": _first_sentence(h.article.body), "severity": "medium"}
                      for h in top[:2]],
        "documents_to_verify": [
            {"document": "Registered title deeds (30-year chain)", "purpose": "Prove the seller's ownership",
             "where_to_get": "Sub-Registrar office (certified copies)"},
            {"document": "Current record of rights and mutation entries", "purpose": "Match revenue records with title",
             "where_to_get": "Tahsildar / state land-records portal"},
            {"document": "Encumbrance certificate + CERSAI search", "purpose": "Detect mortgages and charges",
             "where_to_get": "Sub-Registrar / CERSAI portal"},
        ],
        "next_steps": ["Collect the documents listed above", "Get an advocate's written title report",
                       "Pay only through banking channels against a written agreement"],
        "applicable_laws": [h.article.sources for h in top if h.article.sources],
        "citations": [h.article.id for h in top],
        "clarifying_questions": [],
        "when_to_consult_lawyer": "Before paying more than a token amount or signing any agreement.",
        "confidence": 0.5,
    }


# ---------------------------------------------------------------------------
# agent
# ---------------------------------------------------------------------------

def _passages(hits: list[Hit]) -> str:
    blocks = []
    for h in hits:
        a = h.article
        juris = ", ".join(JURISDICTIONS.get(j, j) for j in a.jurisdictions)
        blocks.append(f"[{a.id}] {a.title}\nJurisdiction: {juris}\nSources: {a.sources}\n{a.body}")
    return "\n\n---\n\n".join(blocks)


def _verify(ai: LegalAnswerAI, hits: list[Hit], warnings: list[str]) -> LegalAnswerAI:
    allowed = {h.article.id for h in hits}
    cited = [c.strip("[] ") for c in ai.citations]
    valid = [c for c in dict.fromkeys(cited) if c in allowed]
    inline = set(_CITE_RE.findall(ai.detailed_answer + " " + ai.summary))
    fabricated = (set(cited) | inline) - allowed
    if fabricated:
        warnings.append(f"Removed {len(fabricated)} citation(s) to passages that were not retrieved: "
                        + ", ".join(sorted(fabricated)))

    def strip(text: str) -> str:
        return _CITE_RE.sub(lambda m: m.group(0) if m.group(1) in allowed else "", text)

    valid = list(dict.fromkeys(valid + [c for c in inline if c in allowed]))
    if not valid and hits and ai.in_scope:
        valid = [h.article.id for h in hits[:2]]
    confidence = ai.confidence
    if not hits:
        confidence = min(confidence, 0.35)
        if ai.in_scope:
            warnings.append("No knowledge-base article matched; the answer relies on the model's general knowledge.")
    return ai.model_copy(update={"citations": valid, "summary": strip(ai.summary),
                                 "detailed_answer": strip(ai.detailed_answer), "confidence": confidence})


def run_agent(inp: LegalInput, image: ProcessedImage | None = None) -> AgentRun:
    index = get_index()
    question = inp.messages[-1].content
    history = _history(inp)
    profile = _profile_text(inp)

    # 1. plan
    plan_res: LLMResult = gateway.generate(
        system=prompts.LEGAL_PLANNER, schema=LegalPlan, history=history, max_tokens=800, fast=True,
        user_text=f"{profile}\nQuestion: {question}", demo=lambda: _demo_plan(inp),
    )
    plan: LegalPlan = plan_res.data

    # 2. retrieve (profile state wins over the planner's guess)
    jurisdiction = inp.jurisdiction or plan.jurisdiction.strip().lower()
    if jurisdiction not in JURISDICTIONS:
        jurisdiction = None
    queries = [question] + [q for q in plan.search_queries if q.strip()][:4]
    if inp.buyer_profile in ("nri", "oci", "foreign_national"):
        queries.append("nri oci foreign fema purchase restriction")
    if inp.property_type == "agricultural_land":
        queries.append("agricultural land purchase restriction conversion")
    hits = index.search(queries, jurisdiction, k=6)

    # 3. answer
    passages = _passages(hits) if hits else "(no matching passages found)"
    user_text = (f"{profile}\nPlanner notes: issues = {', '.join(plan.issue_categories) or 'n/a'}.\n\n"
                 f"KNOWLEDGE BASE PASSAGES:\n{passages}\n\nBUYER'S QUESTION:\n{question}")
    if image:
        user_text += "\n\nA photo of a property document is attached - review it."
    ans_res: LLMResult = gateway.generate(
        system=prompts.LEGAL_ANSWER, schema=LegalAnswerAI, user_text=user_text, history=history,
        images=[image] if image else [], demo=lambda: _demo_answer(hits), max_tokens=4096,
    )

    # 4. verify
    warnings = list(dict.fromkeys(plan_res.warnings + ans_res.warnings))
    ai = _verify(ans_res.data, hits, warnings)
    if plan.needs_clarification:
        ai = ai.model_copy(update={"clarifying_questions":
                                   list(dict.fromkeys(ai.clarifying_questions + plan.clarifying_questions))[:4]})
    cited = set(ai.citations)
    sources = [LegalSource(id=h.article.id, title=h.article.title, jurisdictions=list(h.article.jurisdictions),
                           sources=h.article.sources, excerpt=h.article.excerpt(420), score=round(h.score, 3),
                           cited=h.article.id in cited) for h in hits]
    advice = LegalAdvice(**ai.model_dump(), plan=plan, sources=sources,
                         knowledge_base_articles=len(index.articles), disclaimer=DISCLAIMER)
    return AgentRun(advice, ans_res.mode, ans_res.provider, ans_res.model,
                    plan_res.latency_ms + ans_res.latency_ms, warnings)
