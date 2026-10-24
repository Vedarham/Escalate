"""Strict JSON data contracts shared by the AI layer, the API and the frontend.

Every AI response is validated against one of the `*Report` models below before it
leaves the backend, so the React UI can always rely on the exact same shape.

Design rules for AI-facing models (they are converted to strict JSON schemas):
  * every field is required (no Optional) - use "" / [] / 0 for "unknown"
  * enums are lowercase Literals, normalised before validation
  * numeric ranges are enforced by clamping validators, not by schema keywords
"""
from __future__ import annotations

from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Normalising helpers
# ---------------------------------------------------------------------------


def _lower(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().lower().replace(" ", "_").replace("-", "_")
    return v


def _clamp(lo: float, hi: float):
    def inner(v: Any) -> Any:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return v
        return max(lo, min(hi, f))

    return inner


def _confidence(v: Any) -> Any:
    """Accept 0-1 or 0-100 confidence values and normalise to 0-1."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if f > 1:
        f = f / 100
    return max(0.0, min(1.0, f))


def _str_list(v: Any) -> Any:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    return v


Confidence = Annotated[float, BeforeValidator(_confidence)]
Score100 = Annotated[float, BeforeValidator(_clamp(0, 100))]
Percent = Annotated[float, BeforeValidator(_clamp(0, 100))]
NonNeg = Annotated[float, BeforeValidator(_clamp(0, 1e15))]
StrList = Annotated[list[str], BeforeValidator(_str_list)]

RiskLevel = Annotated[Literal["low", "medium", "high", "critical"], BeforeValidator(_lower)]
Severity = Annotated[Literal["none", "minor", "moderate", "severe", "critical"], BeforeValidator(_lower)]
Likelihood = Annotated[Literal["low", "medium", "high"], BeforeValidator(_lower)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------------------------------------------------------------------------
# Generic API envelope
# ---------------------------------------------------------------------------


class Meta(BaseModel):
    mode: Literal["live", "demo"]
    provider: str
    model: str
    latency_ms: int
    warnings: list[str] = Field(default_factory=list)
    record_id: int | None = None


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: Literal[True] = True
    data: T
    meta: Meta


class ApiError(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ApiError


# ---------------------------------------------------------------------------
# 1. Construction site safety monitoring
# ---------------------------------------------------------------------------


class PPEItem(StrictModel):
    item: str = Field(description="PPE item, e.g. hard hat, high-visibility vest, safety boots, gloves, harness, eye protection")
    status: Annotated[Literal["compliant", "non_compliant", "not_visible", "partial"], BeforeValidator(_lower)]
    workers_affected: Annotated[int, BeforeValidator(_clamp(0, 10_000))] = Field(description="Number of workers this observation applies to (0 if unknown)")
    observation: str


class Hazard(StrictModel):
    category: str = Field(description="e.g. fall from height, struck-by, electrical, excavation, housekeeping, fire, scaffolding, machinery")
    description: str
    severity: RiskLevel
    location_in_image: str = Field(description="Where in the image the hazard is, e.g. 'top-left scaffolding'")
    regulation_reference: str = Field(description="Relevant standard such as an OSHA 1926 subpart or IS code, or '' if unsure")
    recommended_action: str


class SafetyReport(StrictModel):
    scene_summary: str
    overall_risk_level: RiskLevel
    safety_score: Score100 = Field(description="0 (extremely unsafe) to 100 (fully compliant)")
    workers_detected: Annotated[int, BeforeValidator(_clamp(0, 10_000))]
    ppe_compliance: list[PPEItem]
    hazards: list[Hazard]
    positive_observations: StrList
    immediate_actions: StrList
    image_quality_note: str = Field(description="Comment on visibility/quality limits of the image, '' if fine")
    confidence: Confidence = Field(description="0-1 confidence in this assessment")


# ---------------------------------------------------------------------------
# 2. Structural crack detection & analysis
# ---------------------------------------------------------------------------


class Crack(StrictModel):
    crack_type: str = Field(description="hairline, shrinkage, settlement, flexural, shear/diagonal, map/crazing, thermal, corrosion-induced, other")
    orientation: str = Field(description="vertical, horizontal, diagonal, stepped, random/map")
    estimated_width_mm: str = Field(description="Estimated width range in mm, e.g. '0.1-0.3'")
    estimated_length: str
    location: str
    severity: Severity


class ProbableCause(StrictModel):
    cause: str
    likelihood: Likelihood
    explanation: str


class CorrectiveAction(StrictModel):
    action: str
    priority: Annotated[Literal["immediate", "short_term", "monitor"], BeforeValidator(_lower)]
    method: str = Field(description="Repair method/material, e.g. epoxy injection, polymer-modified mortar, stitching")


class CrackReport(StrictModel):
    crack_detected: bool
    surface_description: str
    cracks: list[Crack]
    overall_severity: Severity
    structural_concern: bool
    probable_causes: list[ProbableCause]
    recommended_actions: list[CorrectiveAction]
    monitoring_plan: str
    requires_engineer_inspection: bool
    image_quality_note: str
    confidence: Confidence
    disclaimer: str


# ---------------------------------------------------------------------------
# 3. Real estate valuation
# ---------------------------------------------------------------------------


class ValuationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=2, max_length=200)
    property_type: Literal["apartment", "independent_house", "villa", "plot", "commercial_office", "retail_shop", "warehouse"]
    built_up_area_sqft: float = Field(gt=0, le=1_000_000)
    plot_area_sqft: float = Field(default=0, ge=0, le=10_000_000)
    bedrooms: int = Field(default=0, ge=0, le=50)
    bathrooms: int = Field(default=0, ge=0, le=50)
    age_years: float = Field(default=0, ge=0, le=200)
    floor: int = Field(default=0, ge=-5, le=200)
    condition: Literal["new", "excellent", "good", "fair", "needs_renovation"] = "good"
    amenities: list[str] = Field(default_factory=list, max_length=30)
    currency: Literal["INR", "USD"] = "INR"
    notes: str = Field(default="", max_length=2000)


class ValueRange(StrictModel):
    low: NonNeg
    mid: NonNeg
    high: NonNeg

    @model_validator(mode="after")
    def _ordered(self) -> "ValueRange":
        self.low, self.mid, self.high = sorted([self.low, self.mid, self.high])
        return self


class ValuationFactor(StrictModel):
    factor: str
    impact: Annotated[Literal["positive", "negative", "neutral"], BeforeValidator(_lower)]
    weight_percent: Percent
    explanation: str


class ValuationReport(StrictModel):
    currency: str
    estimated_value: ValueRange
    price_per_sqft: NonNeg
    valuation_factors: list[ValuationFactor]
    market_insights: StrList
    comparable_assumptions: StrList
    image_observations: str = Field(description="What the property photo shows ('' if no photo)")
    rental_yield_percent: Annotated[float, BeforeValidator(_clamp(0, 30))]
    investment_outlook: str
    confidence: Confidence
    disclaimer: str


# ---------------------------------------------------------------------------
# 4. Construction project planning
# ---------------------------------------------------------------------------


class PlanningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(default="New Project", max_length=120)
    project_type: Literal["residential", "commercial", "industrial", "institutional"] = "residential"
    location: str = Field(min_length=2, max_length=200)
    built_up_area_sqft: float = Field(gt=0, le=5_000_000)
    floors: int = Field(default=1, ge=1, le=100)
    structure_type: Literal["rcc_frame", "load_bearing", "steel_frame"] = "rcc_frame"
    quality_tier: Literal["economy", "standard", "premium"] = "standard"
    currency: Literal["INR", "USD"] = "INR"
    start_date: str = Field(default="", max_length=20)
    special_requirements: str = Field(default="", max_length=2000)


class MaterialLine(BaseModel):
    material: str
    quantity: float
    unit: str
    unit_rate: float
    cost: float


class CostLine(BaseModel):
    category: str
    amount: float
    percent: float


class AITask(StrictModel):
    id: str = Field(description="Short unique id like T1, T2")
    task: str
    phase: str = Field(description="e.g. Pre-construction, Substructure, Superstructure, MEP, Finishing, Handover")
    duration_days: Annotated[int, BeforeValidator(_clamp(1, 2000))]
    depends_on: StrList = Field(description="ids of prerequisite tasks")
    resources: str


class Room(StrictModel):
    name: str
    x: Annotated[float, BeforeValidator(_clamp(0, 100))]
    y: Annotated[float, BeforeValidator(_clamp(0, 100))]
    width: Annotated[float, BeforeValidator(_clamp(1, 100))]
    height: Annotated[float, BeforeValidator(_clamp(1, 100))]


class ArchitecturalConcept(StrictModel):
    style: str
    description: str
    design_features: StrList
    sustainability_features: StrList
    facade_palette: StrList = Field(description="3-5 hex colours for the facade, e.g. #d9d4c7")
    floor_plan: list[Room] = Field(description="Typical floor layout on a 100x100 grid; rooms should not overlap")


class PlanningAI(StrictModel):
    """Part of the plan produced by the AI (the rest is computed deterministically)."""

    schedule: list[AITask]
    architectural_concept: ArchitecturalConcept
    risks: StrList
    recommendations: StrList


class ScheduledTask(BaseModel):
    id: str
    task: str
    phase: str
    duration_days: int
    depends_on: list[str]
    resources: str
    start_day: int
    end_day: int
    critical: bool


class PlanningReport(BaseModel):
    project_name: str
    currency: str
    materials: list[MaterialLine]
    cost_breakdown: list[CostLine]
    material_cost: float
    total_cost: float
    cost_per_sqft: float
    contingency: float
    schedule: list[ScheduledTask]
    total_duration_days: int
    critical_path: list[str]
    architectural_concept: ArchitecturalConcept
    risks: list[str]
    recommendations: list[str]
    assumptions: list[str]


# ---------------------------------------------------------------------------
# 5. Daily site assistance & weather advisory
# ---------------------------------------------------------------------------


class DailyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=2, max_length=120)
    project_phase: str = Field(default="Superstructure", max_length=120)
    planned_activities: list[str] = Field(default_factory=list, max_length=20)
    crew_size: int = Field(default=10, ge=0, le=5000)
    concerns: str = Field(default="", max_length=2000)

    @field_validator("planned_activities")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        return [a.strip()[:200] for a in v if a and a.strip()]


class WeatherDay(BaseModel):
    date: str
    temp_max_c: float | None
    temp_min_c: float | None
    precipitation_mm: float | None
    precipitation_probability: float | None
    wind_max_kmh: float | None
    condition: str


class WeatherSnapshot(BaseModel):
    available: bool
    location_name: str
    latitude: float | None = None
    longitude: float | None = None
    current_temp_c: float | None = None
    current_condition: str = ""
    days: list[WeatherDay] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    source: str = "open-meteo.com"


class ActivityAdvice(StrictModel):
    activity: str
    recommendation: Annotated[Literal["proceed", "proceed_with_caution", "postpone"], BeforeValidator(_lower)]
    reason: str
    precautions: StrList


class DailyAdvisoryAI(StrictModel):
    weather_summary: str
    work_suitability: Annotated[Literal["go", "caution", "no_go"], BeforeValidator(_lower)]
    activity_recommendations: list[ActivityAdvice]
    safety_briefing: StrList
    toolbox_talk_topic: str
    material_protection: StrList
    daily_checklist: StrList
    productivity_tips: StrList


class DailyAdvisory(DailyAdvisoryAI):
    weather: WeatherSnapshot


# ---------------------------------------------------------------------------
# 6. Construction knowledge assistant (chat)
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _last_is_user(self) -> "ChatInput":
        if self.messages[-1].role != "user":
            raise ValueError("the last message must come from the user")
        return self


# ---------------------------------------------------------------------------
# 7. Land purchase legal advisory agent (RAG)
# ---------------------------------------------------------------------------

JurisdictionSlug = Literal[
    "", "all-india", "maharashtra", "karnataka", "tamil-nadu", "telangana", "andhra-pradesh",
    "uttar-pradesh", "delhi", "gujarat", "madhya-pradesh", "other",
]


class LegalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    jurisdiction: JurisdictionSlug = ""
    property_type: Literal["unknown", "agricultural_land", "residential_plot", "apartment", "house",
                           "commercial", "industrial"] = "unknown"
    buyer_profile: Literal["resident_indian", "nri", "oci", "foreign_national", "company", "unknown"] = "resident_indian"

    @model_validator(mode="after")
    def _last_is_user(self) -> "LegalInput":
        if self.messages[-1].role != "user":
            raise ValueError("the last message must come from the user")
        return self


class LegalPlan(StrictModel):
    """Planner step output: how the agent will research the question."""

    jurisdiction: str = Field(description="State slug such as maharashtra, karnataka, tamil-nadu, delhi; 'all-india' if not state specific; 'unknown' if unclear")
    issue_categories: StrList = Field(description="e.g. title, inheritance, power of attorney, agricultural restriction, fraud, mortgage, tax, RERA")
    search_queries: StrList = Field(description="2-4 short keyword search queries for the land-law knowledge base, using legal terms")
    needs_clarification: bool
    clarifying_questions: StrList


class RedFlag(StrictModel):
    issue: str
    why_it_matters: str
    severity: RiskLevel


class DocumentCheck(StrictModel):
    document: str
    purpose: str
    where_to_get: str


class LegalAnswerAI(StrictModel):
    in_scope: bool = Field(description="false if the question is not about buying/owning land or property")
    summary: str = Field(description="2-3 sentence direct answer")
    detailed_answer: str = Field(description="Markdown explanation citing passages inline like [TX-04]")
    risk_level: RiskLevel
    red_flags: list[RedFlag]
    documents_to_verify: list[DocumentCheck]
    next_steps: StrList
    applicable_laws: StrList = Field(description="Statutes/judgments named in the cited passages only")
    citations: StrList = Field(description="IDs of knowledge-base passages relied on, e.g. TX-04")
    clarifying_questions: StrList
    when_to_consult_lawyer: str
    confidence: Confidence


class LegalSource(BaseModel):
    id: str
    title: str
    jurisdictions: list[str]
    sources: str
    excerpt: str
    score: float
    cited: bool


class LegalAdvice(LegalAnswerAI):
    plan: LegalPlan
    sources: list[LegalSource]
    knowledge_base_articles: int
    disclaimer: str


class KnowledgeAnswer(StrictModel):
    answer: str = Field(description="Clear answer; may use simple markdown (bold, bullet lists)")
    key_points: StrList
    code_references: StrList = Field(description="Relevant standards e.g. 'IS 456:2000 cl. 26.4', 'ACI 318-19'; [] if none")
    safety_considerations: StrList
    follow_up_questions: StrList
    confidence: Confidence
    in_scope: bool = Field(description="false if the question is unrelated to construction/real estate")
