"""Deterministic construction estimation + schedule (CPM) engine.

Quantities and costs are computed with transparent thumb rules so they are
reproducible and auditable; the AI contributes the schedule draft, architectural
concept and risk narrative, which this module then verifies (dependency cleanup,
cycle breaking, critical-path computation).
"""
from __future__ import annotations

from collections import defaultdict, deque

from ..schemas import AITask, CostLine, MaterialLine, PlanningInput, ScheduledTask

# Quantity per sqft of built-up area (RCC frame, standard spec)
BASE_QTY = {
    "Cement (OPC 53)": (0.40, "bags"),
    "Reinforcement steel (Fe500)": (4.0, "kg"),
    "Fine aggregate (sand)": (1.8, "cft"),
    "Coarse aggregate (20mm)": (1.35, "cft"),
    "Bricks / blocks": (8.0, "nos"),
    "Paint (interior + exterior)": (0.18, "litre"),
    "Flooring tiles": (1.3, "sqft"),
}

UNIT_RATES = {
    "INR": {"Cement (OPC 53)": 420, "Reinforcement steel (Fe500)": 68, "Fine aggregate (sand)": 60,
            "Coarse aggregate (20mm)": 55, "Bricks / blocks": 9, "Paint (interior + exterior)": 300,
            "Flooring tiles": 65},
    "USD": {"Cement (OPC 53)": 14, "Reinforcement steel (Fe500)": 1.2, "Fine aggregate (sand)": 1.5,
            "Coarse aggregate (20mm)": 1.4, "Bricks / blocks": 0.7, "Paint (interior + exterior)": 10,
            "Flooring tiles": 4.5},
}

# Other cost heads as a multiple of core material cost
OTHER_HEADS = {
    "INR": {"Labour": 0.55, "MEP (electrical, plumbing, HVAC)": 0.30, "Doors, windows & fixtures": 0.18,
            "Equipment & site overheads": 0.10, "Design, approvals & supervision": 0.07},
    "USD": {"Labour": 1.60, "MEP (electrical, plumbing, HVAC)": 0.90, "Doors, windows & fixtures": 0.50,
            "Equipment & site overheads": 0.30, "Design, approvals & supervision": 0.20},
}

STRUCTURE_FACTORS = {
    "rcc_frame": {},
    "load_bearing": {"Reinforcement steel (Fe500)": 0.4, "Bricks / blocks": 1.6, "Cement (OPC 53)": 0.9},
    "steel_frame": {"Reinforcement steel (Fe500)": 2.2, "Cement (OPC 53)": 0.6, "Coarse aggregate (20mm)": 0.6,
                    "Fine aggregate (sand)": 0.8},
}
QUALITY = {"economy": (0.95, 0.85), "standard": (1.0, 1.0), "premium": (1.05, 1.35)}  # (qty, rate)
PROJECT_STEEL = {"residential": 1.0, "commercial": 1.1, "industrial": 1.15, "institutional": 1.05}
CONTINGENCY = 0.05


def estimate_costs(p: PlanningInput) -> dict:
    qty_f, rate_f = QUALITY[p.quality_tier]
    struct = STRUCTURE_FACTORS[p.structure_type]
    height_f = 1 + 0.015 * max(0, p.floors - 2)  # taller buildings need more structure
    rates = UNIT_RATES[p.currency]

    materials: list[MaterialLine] = []
    for name, (per_sqft, unit) in BASE_QTY.items():
        q = per_sqft * p.built_up_area_sqft * qty_f * struct.get(name, 1.0)
        if name in ("Reinforcement steel (Fe500)", "Cement (OPC 53)"):
            q *= height_f
        if name == "Reinforcement steel (Fe500)":
            q *= PROJECT_STEEL[p.project_type]
        rate = rates[name] * rate_f
        materials.append(MaterialLine(material=name, quantity=round(q, 1), unit=unit,
                                      unit_rate=round(rate, 2), cost=round(q * rate, 2)))

    material_cost = sum(m.cost for m in materials)
    heads = {"Core materials": material_cost}
    for head, ratio in OTHER_HEADS[p.currency].items():
        heads[head] = material_cost * ratio * (rate_f if head != "Labour" else 1.0)
    subtotal = sum(heads.values())
    contingency = subtotal * CONTINGENCY
    heads["Contingency (5%)"] = contingency
    total = subtotal + contingency

    breakdown = [CostLine(category=k, amount=round(v, 2), percent=round(100 * v / total, 1)) for k, v in heads.items()]
    assumptions = [
        f"Quantities use thumb rules per sqft of built-up area for {p.structure_type.replace('_', ' ')} construction, "
        f"{p.quality_tier} specification.",
        f"Unit rates are indicative {p.currency} market averages and should be replaced with local supplier quotes.",
        "Excludes land cost, taxes/GST, statutory fees, furniture and external development unless stated.",
        f"A {int(CONTINGENCY * 100)}% contingency is included for price escalation and unforeseen work.",
    ]
    return {
        "materials": materials,
        "cost_breakdown": breakdown,
        "material_cost": round(material_cost, 2),
        "total_cost": round(total, 2),
        "cost_per_sqft": round(total / p.built_up_area_sqft, 2),
        "contingency": round(contingency, 2),
        "assumptions": assumptions,
    }


def benchmark_duration(p: PlanningInput) -> int:
    """Rule-of-thumb total duration (working days) used to steer and sanity-check the AI schedule."""
    base = 90 + 0.012 * p.built_up_area_sqft + 30 * p.floors
    factor = {"steel_frame": 0.8, "load_bearing": 0.95, "rcc_frame": 1.0}[p.structure_type]
    factor *= {"economy": 0.9, "standard": 1.0, "premium": 1.15}[p.quality_tier]
    return int(min(2000, round(base * factor)))


def compute_schedule(tasks: list[AITask]) -> tuple[list[ScheduledTask], int, list[str], list[str]]:
    """Clean AI task graph and run the critical path method.

    Returns (scheduled_tasks, total_duration, critical_path_ids, warnings).
    """
    warnings: list[str] = []
    # unique ids
    seen: set[str] = set()
    clean: list[AITask] = []
    for i, t in enumerate(tasks):
        tid = (t.id or f"T{i + 1}").strip() or f"T{i + 1}"
        if tid in seen:
            tid = f"{tid}_{i + 1}"
            warnings.append(f"Duplicate task id renamed to {tid}.")
        seen.add(tid)
        clean.append(t.model_copy(update={"id": tid}))
    ids = {t.id for t in clean}
    deps = {t.id: [d for d in dict.fromkeys(t.depends_on) if d in ids and d != t.id] for t in clean}
    dropped = sum(len(t.depends_on) for t in clean) - sum(len(v) for v in deps.values())
    if dropped:
        warnings.append(f"Removed {dropped} invalid task dependencies from the AI draft.")

    # Kahn topological sort; break cycles by dropping remaining deps of the earliest blocked task
    order: list[str] = []
    remaining = {k: set(v) for k, v in deps.items()}
    position = {t.id: i for i, t in enumerate(clean)}
    while remaining:
        ready = sorted((k for k, v in remaining.items() if not v), key=position.get)
        if not ready:
            victim = min(remaining, key=position.get)
            warnings.append(f"Dependency cycle detected; dependencies of {victim} were removed.")
            deps[victim] = [d for d in deps[victim] if d in order]
            remaining[victim] = set()
            continue
        for k in ready:
            order.append(k)
            del remaining[k]
            for v in remaining.values():
                v.discard(k)

    by_id = {t.id: t for t in clean}
    es: dict[str, int] = {}
    ef: dict[str, int] = {}
    for k in order:
        es[k] = max((ef[d] for d in deps[k]), default=0)
        ef[k] = es[k] + by_id[k].duration_days
    total = max(ef.values(), default=0)

    successors: dict[str, list[str]] = defaultdict(list)
    for k, ds in deps.items():
        for d in ds:
            successors[d].append(k)
    lf: dict[str, int] = {}
    ls: dict[str, int] = {}
    for k in reversed(order):
        lf[k] = min((ls[s] for s in successors[k]), default=total)
        ls[k] = lf[k] - by_id[k].duration_days
    critical = {k for k in order if ls[k] - es[k] == 0}

    # critical path: follow critical chain from a zero-start critical task
    path: list[str] = []
    current = next((k for k in order if k in critical and es[k] == 0), None)
    while current:
        path.append(current)
        nxt = [s for s in successors[current] if s in critical and es[s] == ef[current]]
        current = min(nxt, key=position.get) if nxt else None

    scheduled = [
        ScheduledTask(id=k, task=by_id[k].task, phase=by_id[k].phase, duration_days=by_id[k].duration_days,
                      depends_on=deps[k], resources=by_id[k].resources, start_day=es[k], end_day=ef[k],
                      critical=k in critical)
        for k in sorted(order, key=lambda x: (es[x], position[x]))
    ]
    return scheduled, total, path, warnings
