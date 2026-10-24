"""Construction planning & real-estate valuation module."""
from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, UploadFile

from .. import prompts
from ..schemas import ApiResponse, PlanningAI, PlanningInput, PlanningReport, ValuationInput, ValuationReport
from ..services import demo
from ..services.estimator import benchmark_duration, compute_schedule, estimate_costs
from ..services.llm import gateway
from .common import envelope, parse_payload, read_image

router = APIRouter(tags=["Planning & valuation"])


@router.post("/valuation/estimate", response_model=ApiResponse[ValuationReport])
def estimate_value(
    payload: str | None = Form(None, description="JSON matching ValuationInput"),
    image: UploadFile | None = File(None, description="Optional property photo"),
):
    v = parse_payload(payload, ValuationInput)
    img = read_image(image, required=False)
    brief = v.model_dump()
    user_text = (
        "Estimate the market value of this property. Property details (JSON):\n"
        + json.dumps(brief, indent=1)
        + ("\nA photo of the property is attached." if img else "\nNo photo provided.")
    )
    result = gateway.generate(system=prompts.VALUATION, user_text=user_text, schema=ValuationReport,
                              images=[img] if img else [], demo=lambda: demo.valuation_demo(v, img is not None))
    data: ValuationReport = result.data
    data.currency = v.currency
    if data.estimated_value.mid > 0:
        data.price_per_sqft = round(data.estimated_value.mid / v.built_up_area_sqft, 2)
    title = f"{v.property_type.replace('_', ' ').title()} - {v.location}"
    return envelope("valuation", title, brief, data, result, img)


@router.post("/planning/estimate", response_model=ApiResponse[PlanningReport])
def plan_project(p: PlanningInput):
    costs = estimate_costs(p)
    benchmark = benchmark_duration(p)
    material_summary = ", ".join(f"{m.material}: {m.quantity:g} {m.unit}" for m in costs["materials"])
    user_text = (
        "Project brief (JSON):\n" + p.model_dump_json(indent=1)
        + f"\n\nPre-computed material quantities: {material_summary}."
        + f"\nEstimated total cost: {costs['total_cost']:,.0f} {p.currency} "
          f"({costs['cost_per_sqft']:,.0f} {p.currency}/sqft)."
        + f"\nHistorical benchmark for the critical-path duration of a project like this: about {benchmark} "
          "working days (+/-20%). Size task durations so the longest dependency chain lands near this."
    )
    result = gateway.generate(system=prompts.PLANNING, user_text=user_text, schema=PlanningAI,
                              demo=lambda: demo.planning_demo(p), max_tokens=6000)
    ai: PlanningAI = result.data
    schedule, total_days, critical_path, sched_warnings = compute_schedule(ai.schedule)
    if total_days and abs(total_days - benchmark) / benchmark > 0.4:
        sched_warnings.append(
            f"AI schedule ({total_days} days) differs from the historical benchmark (~{benchmark} days) "
            "by more than 40%; review task durations."
        )
    report = PlanningReport(
        project_name=p.project_name, currency=p.currency, schedule=schedule, total_duration_days=total_days,
        critical_path=critical_path, architectural_concept=ai.architectural_concept, risks=ai.risks,
        recommendations=ai.recommendations, **costs,
    )
    return envelope("planning", f"{p.project_name} - {p.location}", p.model_dump(), report, result,
                    extra_warnings=sched_warnings)
