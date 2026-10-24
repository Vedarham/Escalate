"""Image-based analysis module: site safety monitoring + structural crack analysis."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from .. import prompts
from ..schemas import ApiResponse, CrackReport, SafetyReport
from ..services import demo
from ..services.llm import gateway
from .common import envelope, read_image

router = APIRouter(tags=["Image analysis"])


@router.post("/safety/analyze", response_model=ApiResponse[SafetyReport])
def analyze_safety(
    image: UploadFile | None = File(None, description="Jobsite photo (JPG/PNG/WEBP)"),
    context: str = Form("", max_length=2000, description="Optional notes, e.g. activity in progress"),
    site_type: str = Form("building", max_length=80),
):
    img = read_image(image, required=True)
    user_text = (
        f"Analyse this {site_type} construction site photo for safety hazards and PPE compliance."
        + (f"\nSite notes from the user: {context}" if context.strip() else "")
    )
    result = gateway.generate(system=prompts.SAFETY, user_text=user_text, schema=SafetyReport,
                              images=[img], demo=lambda: demo.safety_demo(context))
    data: SafetyReport = result.data
    extra = [data.image_quality_note] if data.image_quality_note else []
    if data.confidence < 0.35:
        extra.append("Low confidence: the image may not show a construction site clearly.")
    return envelope("safety", f"Safety check - {site_type}", {"context": context, "site_type": site_type},
                    data, result, img, extra)


@router.post("/cracks/analyze", response_model=ApiResponse[CrackReport])
def analyze_crack(
    image: UploadFile | None = File(None, description="Close-up photo of the crack"),
    element_type: str = Form("wall", max_length=60, description="wall, beam, column, slab, foundation, pavement"),
    material: str = Form("", max_length=80),
    building_age_years: float | None = Form(None, ge=0, le=300),
    notes: str = Form("", max_length=2000),
):
    img = read_image(image, required=True)
    details = [f"Structural element: {element_type}"]
    if material:
        details.append(f"Material: {material}")
    if building_age_years is not None:
        details.append(f"Building age: {building_age_years:g} years")
    if notes.strip():
        details.append(f"Observations from the user: {notes}")
    user_text = "Assess the cracks in this photo.\n" + "\n".join(details)
    result = gateway.generate(system=prompts.CRACK, user_text=user_text, schema=CrackReport,
                              images=[img], demo=lambda: demo.crack_demo(element_type))
    data: CrackReport = result.data
    if data.overall_severity in ("severe", "critical") or data.structural_concern:
        data.requires_engineer_inspection = True  # safety guard-rail regardless of model output
    extra = [data.image_quality_note] if data.image_quality_note else []
    return envelope("crack", f"Crack analysis - {element_type}",
                    {"element_type": element_type, "material": material,
                     "building_age_years": building_age_years, "notes": notes},
                    data, result, img, extra)
