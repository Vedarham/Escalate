"""Assistant & advisory engine: daily site assistance with weather + knowledge chat."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from .. import prompts
from ..schemas import ApiResponse, ChatInput, DailyAdvisory, DailyAdvisoryAI, DailyInput, KnowledgeAnswer
from ..services import demo
from ..services.llm import gateway
from ..services.weather import fetch_weather
from .common import envelope, parse_payload, read_image

router = APIRouter(tags=["Assistant & advisory"])


@router.post("/assistant/daily", response_model=ApiResponse[DailyAdvisory])
def daily_advisory(d: DailyInput):
    weather = fetch_weather(d.location)
    activities = d.planned_activities or ["General site work"]
    user_text = (
        f"Site location: {d.location}\nProject phase: {d.project_phase}\nCrew size: {d.crew_size}\n"
        f"Planned activities today: {'; '.join(activities)}\n"
        + (f"Supervisor concerns: {d.concerns}\n" if d.concerns.strip() else "")
        + "\nWeather forecast (JSON):\n" + weather.model_dump_json(exclude={"source"})
    )
    if not weather.available:
        user_text += "\nLive weather is NOT available - say so in weather_summary and give general guidance."
    result = gateway.generate(system=prompts.DAILY, user_text=user_text, schema=DailyAdvisoryAI,
                              demo=lambda: demo.daily_demo(d, weather))
    data = DailyAdvisory(**result.data.model_dump(), weather=weather)
    extra = [] if weather.available else ["Live weather unavailable; advisory uses general guidance."]
    return envelope("daily", f"Daily advisory - {d.location}", d.model_dump(), data, result, extra_warnings=extra)


@router.post("/assistant/chat", response_model=ApiResponse[KnowledgeAnswer])
def knowledge_chat(
    payload: str | None = Form(None, description='JSON: {"messages": [{"role": "user", "content": "..."}]}'),
    image: UploadFile | None = File(None, description="Optional image to discuss"),
):
    chat = parse_payload(payload, ChatInput)
    img = read_image(image, required=False)
    history = [m.model_dump() for m in chat.messages[:-1]][-12:]  # keep the context window small
    question = chat.messages[-1].content
    result = gateway.generate(system=prompts.KNOWLEDGE, user_text=question, schema=KnowledgeAnswer,
                              images=[img] if img else [], history=history, demo=lambda: demo.chat_demo(chat))
    return envelope("chat", question[:80], {"question": question, "turns": len(chat.messages)},
                    result.data, result, img)
