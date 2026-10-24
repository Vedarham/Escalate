"""Land purchase legal advisory agent (RAG over a curated land-law knowledge base)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from ..schemas import ApiResponse, LegalAdvice, LegalInput
from ..services.legal_agent import run_agent
from ..services.legal_kb import JURISDICTIONS, get_index
from ..services.llm import LLMResult
from .common import AppError, envelope, parse_payload, read_image

router = APIRouter(tags=["Land legal advisor"])


@router.post("/legal/ask", response_model=ApiResponse[LegalAdvice])
def ask_legal(
    payload: str | None = Form(None, description='JSON: {"messages": [...], "jurisdiction": "maharashtra", '
                                                 '"property_type": "agricultural_land", "buyer_profile": "nri"}'),
    image: UploadFile | None = File(None, description="Optional photo of a property document (7/12, sale deed, EC...)"),
):
    inp = parse_payload(payload, LegalInput)
    img = read_image(image, required=False)
    run = run_agent(inp, img)
    result = LLMResult(run.advice, run.mode, run.provider, run.model, run.latency_ms, run.warnings)
    question = inp.messages[-1].content
    return envelope("legal", question[:80],
                    {"question": question, "jurisdiction": inp.jurisdiction, "property_type": inp.property_type,
                     "buyer_profile": inp.buyer_profile, "turns": len(inp.messages)},
                    run.advice, result, img)


@router.get("/legal/kb")
def knowledge_base():
    index = get_index()
    items = [{"id": a.id, "title": a.title, "jurisdictions": list(a.jurisdictions), "topics": list(a.topics)}
             for a in index.articles]
    return {"success": True, "data": {"articles": items, "jurisdictions": JURISDICTIONS}}


@router.get("/legal/kb/{article_id}")
def knowledge_article(article_id: str):
    a = get_index().get(article_id)
    if not a:
        raise AppError("not_found", f"Knowledge-base article {article_id} does not exist.", 404)
    return {"success": True, "data": {"id": a.id, "title": a.title, "jurisdictions": list(a.jurisdictions),
                                      "topics": list(a.topics), "sources": a.sources, "body": a.body}}
