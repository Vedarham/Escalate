"""Deterministic demo responses used when no LLM key is configured (or DEMO_MODE=true).

They follow exactly the same JSON contracts as live AI output, so the UI, tests and
demonstrations behave identically in offline mode.
"""
from __future__ import annotations

import hashlib

from ..schemas import (
    ChatInput, DailyInput, PlanningInput, ValuationInput, WeatherSnapshot,
)

DEMO_NOTE = "[Demo mode] "


def safety_demo(context: str = "") -> dict:
    return {
        "scene_summary": DEMO_NOTE + "Multi-storey RCC building under construction with scaffolding on the east face, "
                         "rebar work on the slab and material stacked near the site entrance."
                         + (f" Context provided: {context[:120]}" if context else ""),
        "overall_risk_level": "high",
        "safety_score": 58,
        "workers_detected": 6,
        "ppe_compliance": [
            {"item": "Hard hat", "status": "partial", "workers_affected": 2, "observation": "Two workers on the slab are not wearing helmets."},
            {"item": "High-visibility vest", "status": "non_compliant", "workers_affected": 4, "observation": "Most workers lack hi-vis vests near moving equipment."},
            {"item": "Fall-arrest harness", "status": "non_compliant", "workers_affected": 1, "observation": "Worker at slab edge (>2 m) without harness or anchorage."},
            {"item": "Safety boots", "status": "not_visible", "workers_affected": 0, "observation": "Footwear not clearly visible in the image."},
        ],
        "hazards": [
            {"category": "Fall from height", "description": "Unprotected slab edge without guardrails or toe boards.",
             "severity": "critical", "location_in_image": "top-right slab edge",
             "regulation_reference": "OSHA 1926.501(b)(1); IS 3696 (Part 1)",
             "recommended_action": "Install 1 m guardrails with mid-rail and toe board before work resumes."},
            {"category": "Scaffolding", "description": "Scaffold bay missing bracing and platform boards are not fully planked.",
             "severity": "high", "location_in_image": "left side scaffolding",
             "regulation_reference": "OSHA 1926.451; IS 4014",
             "recommended_action": "Tag scaffold as unsafe, complete bracing and full planking, re-inspect by competent person."},
            {"category": "Housekeeping / trip", "description": "Rebar offcuts and debris scattered on the access path.",
             "severity": "medium", "location_in_image": "bottom-center walkway",
             "regulation_reference": "OSHA 1926.25",
             "recommended_action": "Clear debris, cap protruding rebar ends, mark a clean pedestrian route."},
        ],
        "positive_observations": ["Materials are stacked on pallets off the ground.", "Site boundary is barricaded."],
        "immediate_actions": [
            "Stop work at the unprotected slab edge until guardrails are fixed.",
            "Issue helmets and hi-vis vests to all workers on the slab.",
            "Inspect and tag the scaffolding before reuse.",
            "Cap all exposed rebar ends.",
        ],
        "image_quality_note": "",
        "confidence": 0.72,
    }


def crack_demo(element: str = "wall") -> dict:
    return {
        "crack_detected": True,
        "surface_description": DEMO_NOTE + f"Plastered masonry {element or 'wall'} surface with visible cracking near a window opening.",
        "cracks": [
            {"crack_type": "Diagonal (shear/settlement)", "orientation": "diagonal", "estimated_width_mm": "0.5-1.5",
             "estimated_length": "~0.8 m", "location": "Running 45 degrees from the lower window corner", "severity": "moderate"},
            {"crack_type": "Hairline shrinkage", "orientation": "random/map", "estimated_width_mm": "<0.1",
             "estimated_length": "multiple short cracks", "location": "Plaster surface right of the opening", "severity": "minor"},
        ],
        "overall_severity": "moderate",
        "structural_concern": True,
        "probable_causes": [
            {"cause": "Differential foundation settlement", "likelihood": "high",
             "explanation": "Diagonal cracks radiating from opening corners are typical of uneven settlement."},
            {"cause": "Missing or inadequate lintel/sill band", "likelihood": "medium",
             "explanation": "Stress concentrates at the corners of openings without proper reinforcement."},
            {"cause": "Plaster drying shrinkage", "likelihood": "high",
             "explanation": "Map-pattern hairline cracks indicate rapid drying or rich cement mortar."},
        ],
        "recommended_actions": [
            {"action": "Install crack-width monitoring gauges (tell-tales)", "priority": "immediate",
             "method": "Glass/plastic tell-tales; record readings weekly for 8-12 weeks."},
            {"action": "Seal and stitch the diagonal crack once movement has stabilised", "priority": "short_term",
             "method": "Rake out, epoxy/PU injection and helical stainless steel stitching bars."},
            {"action": "Repair hairline plaster cracks", "priority": "monitor",
             "method": "Fill with elastomeric crack filler and repaint with crack-bridging coating."},
        ],
        "monitoring_plan": "Measure crack width weekly; escalate if the width grows by more than 0.5 mm or new cracks appear.",
        "requires_engineer_inspection": True,
        "image_quality_note": "",
        "confidence": 0.68,
        "disclaimer": "AI-assisted screening only; confirm with an on-site inspection by a qualified structural engineer.",
    }


_CITY_RATES_INR = {
    "mumbai": 22000, "delhi": 14000, "gurgaon": 12000, "gurugram": 12000, "noida": 8000, "bangalore": 10500,
    "bengaluru": 10500, "hyderabad": 8500, "chennai": 9000, "pune": 9500, "kolkata": 7000, "ahmedabad": 6500,
}
_CITY_RATES_USD = {"new york": 1400, "san francisco": 1100, "los angeles": 800, "chicago": 350, "austin": 380,
                   "seattle": 650, "boston": 750, "miami": 600, "houston": 220, "dallas": 260}


def valuation_demo(v: ValuationInput, has_image: bool) -> dict:
    loc = v.location.lower()
    table, default = (_CITY_RATES_INR, 6000) if v.currency == "INR" else (_CITY_RATES_USD, 300)
    rate = next((r for city, r in table.items() if city in loc), default)
    type_f = {"apartment": 1.0, "independent_house": 1.15, "villa": 1.35, "plot": 0.7, "commercial_office": 1.25,
              "retail_shop": 1.5, "warehouse": 0.55}[v.property_type]
    cond_f = {"new": 1.08, "excellent": 1.04, "good": 1.0, "fair": 0.92, "needs_renovation": 0.8}[v.condition]
    age_f = max(0.6, 1 - 0.01 * v.age_years)
    amen_f = 1 + min(0.1, 0.012 * len(v.amenities))
    ppsf = rate * type_f * cond_f * age_f * amen_f
    mid = ppsf * v.built_up_area_sqft
    return {
        "currency": v.currency,
        "estimated_value": {"low": round(mid * 0.9), "mid": round(mid), "high": round(mid * 1.1)},
        "price_per_sqft": round(ppsf),
        "valuation_factors": [
            {"factor": "Location & micro-market", "impact": "positive", "weight_percent": 40,
             "explanation": f"Benchmark rate for {v.location} drives most of the value."},
            {"factor": "Property type", "impact": "positive" if type_f >= 1 else "negative", "weight_percent": 15,
             "explanation": f"{v.property_type.replace('_', ' ').title()} adjustment factor {type_f:.2f}."},
            {"factor": "Age & depreciation", "impact": "negative" if v.age_years > 5 else "neutral", "weight_percent": 15,
             "explanation": f"{v.age_years:g} years old; about 1% depreciation per year applied."},
            {"factor": "Condition", "impact": "positive" if cond_f > 1 else ("negative" if cond_f < 1 else "neutral"),
             "weight_percent": 15, "explanation": f"Condition '{v.condition}' adjustment {cond_f:.2f}."},
            {"factor": "Amenities", "impact": "positive" if v.amenities else "neutral", "weight_percent": 15,
             "explanation": f"{len(v.amenities)} amenities listed."},
        ],
        "market_insights": [
            DEMO_NOTE + "Values are based on a static benchmark table, not live market data.",
            "Ready-to-move properties typically command a 5-10% premium over under-construction stock.",
        ],
        "comparable_assumptions": [f"Average resale rate of about {rate:,} {v.currency}/sqft for comparable stock in the area."],
        "image_observations": "Photo received; demo mode does not analyse images." if has_image else "",
        "rental_yield_percent": 3.2 if v.currency == "INR" else 5.5,
        "investment_outlook": "Stable demand expected; verify with recent registered transactions before deciding.",
        "confidence": 0.45,
        "disclaimer": "Indicative AI estimate only, not a certified valuation report.",
    }


def planning_demo(p: PlanningInput) -> dict:
    scale = max(0.6, min(3.0, (p.built_up_area_sqft / 2500) ** 0.4))
    f = p.floors

    def d(base: float) -> int:
        return max(1, round(base * scale))

    schedule = [
        {"id": "T1", "task": "Design approvals & permits", "phase": "Pre-construction", "duration_days": d(30), "depends_on": [], "resources": "Architect, liaison consultant"},
        {"id": "T2", "task": "Site clearing, survey & mobilisation", "phase": "Pre-construction", "duration_days": d(7), "depends_on": ["T1"], "resources": "Surveyor, JCB, 6 labourers"},
        {"id": "T3", "task": "Excavation & foundation", "phase": "Substructure", "duration_days": d(25), "depends_on": ["T2"], "resources": "Excavator, 12 labourers, bar benders"},
        {"id": "T4", "task": "Plinth beam & backfilling", "phase": "Substructure", "duration_days": d(10), "depends_on": ["T3"], "resources": "Carpenters, masons"},
        {"id": "T5", "task": f"Columns, beams & slabs ({f} floor{'s' if f > 1 else ''})", "phase": "Superstructure", "duration_days": d(22) * f, "depends_on": ["T4"], "resources": "Formwork crew, RMC supply, concrete pump"},
        {"id": "T6", "task": "Masonry / blockwork", "phase": "Superstructure", "duration_days": d(12) * f, "depends_on": ["T5"], "resources": "Masons, helpers"},
        {"id": "T7", "task": "Electrical & plumbing rough-in", "phase": "MEP", "duration_days": d(18), "depends_on": ["T6"], "resources": "Electricians, plumbers"},
        {"id": "T8", "task": "Plastering (internal & external)", "phase": "Finishing", "duration_days": d(20), "depends_on": ["T7"], "resources": "Plaster crew"},
        {"id": "T9", "task": "Waterproofing & roof treatment", "phase": "Finishing", "duration_days": d(8), "depends_on": ["T5"], "resources": "Waterproofing contractor"},
        {"id": "T10", "task": "Flooring & tiling", "phase": "Finishing", "duration_days": d(18), "depends_on": ["T8"], "resources": "Tile layers"},
        {"id": "T11", "task": "Doors, windows & fixtures", "phase": "Finishing", "duration_days": d(12), "depends_on": ["T8"], "resources": "Carpenters, fabricators"},
        {"id": "T12", "task": "Painting & final MEP fit-out", "phase": "Finishing", "duration_days": d(15), "depends_on": ["T10", "T11", "T9"], "resources": "Painters, electricians, plumbers"},
        {"id": "T13", "task": "Snagging, cleaning & handover", "phase": "Handover", "duration_days": d(7), "depends_on": ["T12"], "resources": "Site engineer, QA team"},
    ]
    floor_plan = [
        {"name": "Living / Lobby", "x": 0, "y": 0, "width": 55, "height": 45},
        {"name": "Kitchen", "x": 55, "y": 0, "width": 45, "height": 30},
        {"name": "Dining", "x": 55, "y": 30, "width": 45, "height": 15},
        {"name": "Bedroom 1", "x": 0, "y": 45, "width": 40, "height": 35},
        {"name": "Stair / Lift", "x": 40, "y": 45, "width": 20, "height": 25},
        {"name": "Bedroom 2", "x": 60, "y": 45, "width": 40, "height": 35},
        {"name": "Bath 1", "x": 40, "y": 70, "width": 20, "height": 30},
        {"name": "Utility", "x": 0, "y": 80, "width": 40, "height": 20},
        {"name": "Balcony", "x": 60, "y": 80, "width": 40, "height": 20},
    ]
    return {
        "schedule": schedule,
        "architectural_concept": {
            "style": "Contemporary tropical modern" if p.currency == "INR" else "Contemporary modern",
            "description": DEMO_NOTE + f"A {p.project_type} building in {p.location} with clean horizontal lines, deep "
                           "overhangs for shading, and cross-ventilated plans.",
            "design_features": ["Deep sunshades on south/west windows", "Double-height entrance", "Large openings for cross-ventilation"],
            "sustainability_features": ["Rainwater harvesting", "Rooftop solar PV", "Fly-ash bricks / AAC blocks", "LED lighting with daylight sensors"],
            "facade_palette": ["#e9e4da", "#8c7b6b", "#3f4a4f", "#c9a66b"],
            "floor_plan": floor_plan,
        },
        "risks": [
            "Monsoon or seasonal rain delaying substructure works.",
            "Price escalation of steel and cement during the project.",
            "Approval delays from local authorities.",
            "Shortage of skilled labour during festival seasons.",
        ],
        "recommendations": [
            "Lock in steel and cement prices with suppliers for the structural phase.",
            "Use ready-mix concrete for consistent quality and faster slab cycles.",
            "Schedule excavation outside the rainy season.",
            "Hold weekly progress reviews against the critical path.",
        ],
    }


def daily_demo(d: DailyInput, weather: WeatherSnapshot) -> dict:
    alerts = weather.alerts
    rainy = any("rain" in a.lower() for a in alerts)
    windy = any("wind" in a.lower() for a in alerts)
    activities = d.planned_activities or ["General site work"]
    recs = []
    for a in activities:
        al = a.lower()
        if rainy and any(k in al for k in ("concrete", "pour", "slab", "excavat", "plaster")):
            recs.append({"activity": a, "recommendation": "postpone", "reason": "Rain expected; quality and safety risk.",
                         "precautions": ["Cover fresh concrete with polythene sheets", "Reschedule to the next dry window"]})
        elif windy and any(k in al for k in ("crane", "lift", "height", "scaffold", "roof")):
            recs.append({"activity": a, "recommendation": "postpone", "reason": "High winds forecast.",
                         "precautions": ["Secure loose materials", "Lower crane hook and slew freely"]})
        else:
            recs.append({"activity": a, "recommendation": "proceed_with_caution" if alerts else "proceed",
                         "reason": "Conditions acceptable" + (" with weather precautions." if alerts else "."),
                         "precautions": ["Conduct pre-task briefing", "Verify PPE before starting"]})
    suit = "no_go" if all(r["recommendation"] == "postpone" for r in recs) else ("caution" if alerts else "go")
    today = weather.days[0] if weather.days else None
    summary = (f"{today.condition}, {today.temp_min_c}-{today.temp_max_c} C, rain {today.precipitation_mm} mm, "
               f"gusts {today.wind_max_kmh} km/h." if today else "Weather data unavailable.")
    return {
        "weather_summary": DEMO_NOTE + summary,
        "work_suitability": suit,
        "activity_recommendations": recs,
        "safety_briefing": ["Mandatory PPE check at the gate", "Barricade open edges and shafts",
                            f"Crew of {d.crew_size}: assign a first-aider and a fire watcher"],
        "toolbox_talk_topic": "Working safely in today's weather conditions",
        "material_protection": ["Store cement bags on raised platforms under cover", "Cover sand and aggregate stockpiles"],
        "daily_checklist": ["Permit-to-work issued for hot work and height work", "Scaffold tags checked",
                            "Housekeeping round at 12:00 and 17:00", "Daily progress report submitted"],
        "productivity_tips": ["Sequence indoor finishing work as a fallback for weather delays",
                              "Pre-stage materials before the crew arrives"],
    }


_KB = {
    "curing": ("Concrete should be kept moist for **at least 7 days** for OPC and **10-14 days** for blended cements "
               "(PPC/PSC) or in hot, dry weather. Use ponding on slabs, wet hessian on columns, or curing compound.",
               ["IS 456:2000 cl. 13.5.1"]),
    "cover": ("Typical nominal cover (IS 456, moderate exposure): slabs **30 mm**, beams **30 mm**, columns **40 mm**, "
              "footings **50 mm**. Increase for severe exposure.", ["IS 456:2000 Table 16"]),
    "mix": ("Common nominal mixes: M15 = 1:2:4, M20 = 1:1.5:3. For M25 and above use design mixes as per IS 10262.",
            ["IS 456:2000 Table 9", "IS 10262:2019"]),
}


def chat_demo(c: ChatInput) -> dict:
    q = c.messages[-1].content.lower()
    key = next((k for k in _KB if k in q), None)
    if key:
        answer, refs = _KB[key]
    else:
        h = int(hashlib.md5(q.encode()).hexdigest(), 16) % 3
        answer = ["The knowledge assistant is running in **demo mode**. Add a GROQ_API_KEY or HF_TOKEN to the "
                  "backend .env to get full AI answers. Try asking about *curing*, *cover* or *mix* ratios to see sample answers.",
                  "Demo mode is active, so only a few sample topics are answered (curing, cover, mix design). "
                  "Configure an API key for complete answers.",
                  "This is a demo response. Live answers require an LLM API key in the backend configuration."][h]
        refs = []
    return {
        "answer": DEMO_NOTE + answer,
        "key_points": ["Follow the governing code for your region", "Verify with the project's structural engineer"],
        "code_references": refs,
        "safety_considerations": ["Use appropriate PPE while handling cement and admixtures"],
        "follow_up_questions": ["What is the minimum curing period for PPC concrete?", "What cover is needed for footings?"],
        "confidence": 0.6 if key else 0.2,
        "in_scope": True,
    }
