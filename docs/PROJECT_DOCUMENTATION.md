# Escalate: AI-Powered Multimodal Construction Intelligence Platform (Project Documentation)

## Contents
1. [Pre-requisites](#pre-requisites)
2. [Project Workflow](#project-workflow)
3. [Epic 1: Requirements Specification and Environment Setup](#epic-1--requirements-specification-and-environment-setup)
4. [Epic 2: Image-Based Analysis Module Development](#epic-2-image-based-analysis-module-development)
5. [Epic 3: Construction Planning and Valuation Module Development](#epic-3--construction-planning-and-valuation-module-development)
6. [Epic 4: AI Intelligence Layer Implementation](#epic-4--ai-intelligence-layer-implementation)
7. [Epic 5: Assistant and Advisory Engine Development](#epic-5--assistant-and-advisory-engine-development)
8. [Epic 6: Interface, Testing, and Deployment](#epic-6--interface-testing-and-deployment)

---

## Pre-requisites

| Area | Requirement |
|---|---|
| Runtime | Python 3.10+ (developed on 3.12.7), Node.js 20.19+ / 22.12+ (developed on 22.13), npm 10+ |
| Backend libraries | FastAPI, Uvicorn, Pydantic v2, `openai` client (OpenAI-compatible APIs), python-multipart, python-dotenv, httpx, Pillow, pytest |
| Frontend libraries | React 19, React Router 7, Vite 8 (`@vitejs/plugin-react`) |
| AI access (free) | Groq API key (`console.groq.com`) and/or Hugging Face token with Inference Providers credits |
| External data | Open-Meteo geocoding and forecast API (free, no key) |
| Knowledge | REST APIs, React hooks, JSON Schema, prompt engineering, basic construction concepts (PPE, crack types, IS 456 / OSHA 1926, CPM scheduling) |

## Project Workflow

```
User (browser)
   │  text / images / project data / questions
   ▼
React + Vite frontend ── FormData / JSON ──►  FastAPI backend (/api)
   ▲                                             │ 1. validate input (Pydantic, image checks)
   │                                             │ 2. enrich (weather, deterministic estimates)
   │                                             │ 3. LLM gateway → Groq (vision / text model)
   │                                             │       ↳ fallback → Hugging Face
   │                                             │ 4. parse → validate → repair → normalise JSON
   │                                             │ 5. post-process (CPM, guard-rails, warnings)
   │                                             │ 6. persist to SQLite + uploads/
   └──────────── { success, data, meta } ◄───────┘
```

1. **Input.** The user picks a module and submits an image, a form or a chat message. The client checks file type and size first.
2. **Validation.** The backend rejects malformed payloads, wrong file types, empty, corrupted or truncated images, and images that are too small or too large. Each rejection has a specific error code.
3. **Context enrichment.** Image quality heuristics (dark, low contrast, blurry, low resolution), live weather with rule-based alerts, and deterministic quantity and cost estimates are added to the prompt.
4. **Multimodal inference.** The vision model is used when an image is attached and the text model otherwise. A strict JSON schema is enforced.
5. **Verification.** JSON is extracted, validated and normalised, with a one-shot self-repair. Code-level guard-rails are applied: schedule CPM, engineer-inspection rule, and ordered value ranges.
6. **Delivery and storage.** The result is stored and returned in a typed envelope. The UI renders cards, charts, a Gantt chart and a floor plan, and offers a "View JSON contract" toggle.

---

## Epic 1: Requirements Specification and Environment Setup

**Functional requirements**
| ID | Requirement | Implemented in |
|---|---|---|
| FR-1 | Analyse site photos for hazards and PPE compliance | `routers/analysis.py` → `/api/safety/analyze` |
| FR-2 | Detect and classify cracks, with severity, causes and repairs | `/api/cracks/analyze` |
| FR-3 | Estimate real-estate value from data and an optional photo | `routers/planning.py` → `/api/valuation/estimate` |
| FR-4 | Material estimation, cost calculation, scheduling, architectural concept | `/api/planning/estimate`, `services/estimator.py` |
| FR-5 | Daily weather-aware site advisory | `routers/assistant.py` → `/api/assistant/daily` |
| FR-6 | Construction knowledge Q&A with image support | `/api/assistant/chat` |
| FR-7 | Persist and review analysis history | `routers/system.py` → `/api/history` |
| FR-8 | Answer land-purchase legal questions (title, ownership, common issues) with cited sources | `routers/legal.py` → `/api/legal/ask` |

**Non-functional requirements:** strict JSON contracts (`schemas.py`); secrets only in environment variables (`.env`, git-ignored); graceful degradation (provider fallback, demo mode, weather-unavailable mode); a responsive UI down to 375 px; consistent error envelopes; and automated test coverage.

**Environment setup**
- `backend/requirements.txt`, `backend/.env.example`, `app/config.py`. Settings are loaded from `.env` with python-dotenv. Keys are never logged or returned. `/api/health` reports only provider names and models.
- `frontend/package.json`, `vite.config.js`. The dev server proxies `/api` to `:8000`, so no CORS setup is needed in development.
- Deployment is done by the project owner through GitHub and Vercel. [DEPLOYMENT.md](DEPLOYMENT.md) lists what the platform needs; serverless constraints (read-only filesystem, request size limit) are handled in code.

## Epic 2: Image-Based Analysis Module Development

**Multimodal input** (`services/images.py`)
- Accepts JPEG, PNG, WEBP, BMP and GIF. Images are verified with Pillow (`verify()` plus a full `load()`), so truncated or incomplete uploads are detected.
- Rejects empty uploads, non-images, files over `MAX_IMAGE_MB` (413) and images smaller than 64 px.
- Quality heuristics raise warnings for dark, over-exposed, low-contrast, blurry or low-resolution images. These warnings are passed to the model, which then lowers its confidence, and are shown to the user.
- Images are normalised to RGB JPEG with a longest side of at most 1600 px, which reduces tokens and latency, and sent as a base64 data URL.

**Safety monitoring** (`SafetyReport`): scene summary; overall risk (`low|medium|high|critical`); safety score 0–100; workers detected; a PPE table (`compliant|non_compliant|not_visible|partial`, with workers affected); hazards with category, severity, location in the image, OSHA 1926 / IS reference and corrective action; positive observations; immediate actions; confidence. The prompt forbids guessing (unseen PPE must be reported as `not_visible`) and handles images that are not construction sites.

**Crack analysis** (`CrackReport`): a list of cracks (type, orientation, width range in mm, length, location, severity on an explicit mm-based scale); overall severity; structural concern; probable causes with likelihood; corrective actions with priority (`immediate|short_term|monitor`) and repair method; monitoring plan; an engineer-inspection flag, which the server forces on for severe or structural cases; and a disclaimer.

## Epic 3: Construction Planning and Valuation Module Development

**Material estimation and costing** (`services/estimator.py`, deterministic)
- Thumb-rule quantities per sqft: cement, steel, sand, aggregate, bricks/blocks, paint and tiles. They are adjusted for structure type (RCC frame, load-bearing, steel frame), quality tier, building height (+1.5% steel and cement per floor above G+1) and project type.
- Indicative INR and USD unit rates. Other cost heads (labour, MEP, doors and windows, overheads, design) are calculated as ratios of material cost, plus a 5% contingency. The output includes cost per sqft and a list of assumptions.

**Task scheduling** (AI draft + CPM verification)
- The AI proposes 10–18 tasks with durations and dependencies. It is steered by a historical duration benchmark (`benchmark_duration`).
- The code deduplicates IDs, removes invalid or self dependencies, breaks cycles, then computes early and late start and finish, the critical tasks and the critical path. The UI renders a Gantt chart with critical tasks outlined.
- A warning is added when the AI schedule differs from the benchmark by more than 40%.

**Architectural visualisation:** the AI returns a style, description, design and sustainability features, a facade colour palette and a non-overlapping room layout on a 100×100 grid. The frontend draws this as an SVG floor plan.

**Real-estate valuation** (`ValuationReport`): low/mid/high value (sorted by the server), price per sqft (recomputed from mid ÷ area), value drivers with impact and weight, market insights, comparable assumptions, photo observations, gross rental yield, investment outlook, confidence and a disclaimer. Inputs are validated: area > 0, an enumerated property type, and no unknown fields.

## Epic 4: AI Intelligence Layer Implementation

`services/llm.py` is the **LLM gateway**:
- **Providers:** Groq (primary) and Hugging Face Inference Providers (fallback). Both use the OpenAI-compatible API through the `openai` SDK with a custom `base_url`. The order is set by `LLM_PROVIDER`.
- **Model routing:** the vision model (`qwen/qwen3.8-27b`) is used when an image is attached, and the text model (`openai/gpt-oss-120b`) otherwise.
- **Strict schemas:** `strict_schema()` inlines `$ref`s, marks every property required, sets `additionalProperties: false` and drops keywords that strict mode does not support. The schema is also embedded in the system prompt for providers without constrained decoding.
- **Format degradation:** `json_schema` → `json_object` → none. Whichever level a provider/model accepts is cached.
- **Output hygiene:** `<think>…</think>` blocks and markdown fences are stripped, and the outermost JSON object is extracted. Truncated output (`finish_reason=length`) is detected.
- **Self-repair:** validation errors are sent back to the model once for correction.
- **Resilience:** rate limits, timeouts, auth/permission errors, 402 "out of credits", 5xx responses and invalid output all trigger the next provider. If every provider fails, the API returns `502 ai_unavailable` with per-provider details, or labelled demo data when `FALLBACK_TO_DEMO=true`.
- **Normalisation in contracts:** case-insensitive enums, confidence given on 0–100 or 0–1 scales, clamped scores, and a single string coerced to a list.
- **Demo mode** (`services/demo.py`): deterministic, input-aware responses that follow the same contracts.

## Epic 5: Assistant and Advisory Engine Development

**Daily site assistance and weather advisory** (`/api/assistant/daily`)
- `services/weather.py` geocodes the city and fetches the current conditions and a 3-day forecast (temperature, rain, rain probability, wind gusts, WMO condition) from Open-Meteo.
- Rule-based construction alerts: heavy rain over 5 mm (no pours or open excavation), rain probability ≥ 60%, gusts over 40 km/h (no crane or height work), heat ≥ 35 °C or ≥ 38 °C, cold ≤ 5 °C, and thunderstorms.
- The AI combines the forecast, the alerts, the activities, crew size and concerns into `DailyAdvisory`: weather summary, `go|caution|no_go`, per-activity `proceed|proceed_with_caution|postpone` with reasons and precautions, safety briefing, toolbox talk, material protection, checklist and productivity tips.
- If the weather service is unreachable, the advisory still runs on general guidance and a warning is shown.

**Construction knowledge assistant** (`/api/assistant/chat`)
- Multi-turn history (last 12 turns are sent), optional image attachment, and validated roles (the last message must be from the user, and `system` messages from clients are rejected).
- Output `KnowledgeAnswer`: a markdown answer (rendered safely without `innerHTML`), key points, code references (the prompt forbids invented clause numbers), safety considerations, follow-up questions shown as clickable chips, confidence, and an `in_scope` flag for off-topic questions.

**Land purchase legal advisor (RAG agent)** (`/api/legal/ask`, `/api/legal/kb`)

*Why RAG rather than the model on its own:* legal answers must be grounded, citable and state-aware. A model alone tends to invent section numbers and to mix up rules that differ between states. A curated knowledge base keeps answers verifiable and makes the law easy to update without retraining.

- **Knowledge base** (`app/knowledge/land_law/*.md`, 58 articles). Each article has an ID, title, jurisdiction, topics and sources (statutes and judgments). Coverage:
  - title and ownership: marketable title, 30-year search, sale deed vs agreement, registration, mutation, encumbrance certificates, possession, bona fide purchaser;
  - transactions: earnest money, s.53A part performance, specific performance, GPA sales (*Suraj Lamp*), lis pendens, stamp duty, TDS 194-IA, payments, RERA, co-owners;
  - succession: heirs, daughters' coparcenary rights (*Vineeta Sharma*), legal heir certificates and probate, minors' shares, partition, wills;
  - land restrictions: agricultural eligibility, NA conversion, government, assigned and tribal land, acquisition and reservations, forest and CRZ land, NRI/OCI purchases under FEMA, leasehold, trust and Wakf land;
  - disputes and fraud: fraud red flags and remedies, mortgages and CERSAI, adverse possession, encroachment, easements, benami, tenants;
  - due-diligence checklists;
  - state records for Maharashtra, Karnataka, Tamil Nadu, Telangana and Andhra Pradesh, Uttar Pradesh, Delhi, Gujarat and Madhya Pradesh.
- **Agent pipeline** (`services/legal_agent.py`):
  1. **Planner** (fast model `openai/gpt-oss-20b`): identifies the jurisdiction and issue categories, writes 2–4 legal search queries, and flags missing facts.
  2. **Retriever** (`services/legal_kb.py`): a BM25 index over title, topics, sources and body; a legal synonym table (satbara → 7/12, EC → encumbrance certificate, GPA → power of attorney…); "will" treated as a verb or a noun depending on context; max-fusion across queries; a state boost (×1.35 for the selected state, ×0.45 for other states' articles); and a weak-tail cut-off.
  3. **Answerer** (text model, or the vision model when a document photo is attached): `LegalAnswerAI` with summary, cited markdown answer, buyer risk level, red flags, documents to verify (what, why, where), next steps, applicable laws (only those named in the passages), clarifying questions, when to consult a lawyer, and confidence. The document image is treated as data; instructions written inside it are ignored.
  4. **Verifier** (code): keeps only citations to retrieved passages, strips fabricated `[IDs]` from the text with a warning, falls back to the top passages when nothing is cited, and caps confidence when nothing was retrieved.
- **Profile inputs:** state, property type (agricultural land, plot, apartment…) and buyer type (resident, NRI, OCI, foreign national, company). NRI buyers and agricultural land automatically add targeted retrieval queries.
- **UI** (`pages/Legal.jsx`): profile panel, document upload, knowledge-base browser, conversation, a risk badge, citation chips that open the full source article, red flags, a documents table, next steps, the sources searched (cited or retrieved) and the agent's plan.
- **Quality:** a 25-question retrieval evaluation (recall@5 = 100%) and citation-verifier tests run with the test suite. Live checks on Groq produced grounded, high-risk warnings for unsafe deals (non-farmer buying farmland, GPA sale, NRI farmhouse, mortgaged land) and declined off-topic questions.

## Epic 6: Interface, Testing, and Deployment

**Interface** (`frontend/src`)
- Sidebar navigation for the Dashboard, the seven modules (including the Land Legal Advisor) and History. On phones the sidebar becomes a slide-in menu.
- Shared components: drag-and-drop `ImageUpload` with client-side validation and preview, `ScoreRing`, `Badge` (severity colour mapping), `Confidence`, `ResultMeta` (live or demo, provider, model, latency, warnings, "View JSON contract"), `ErrorBanner` (shows field-level validation details), `GanttChart`, `FloorPlan`, `BarList`, and a safe `Markdown` renderer with clickable citation chips.
- Photos are downscaled in the browser (at most 1600 px JPEG) before upload, which keeps requests under serverless body limits.
- Stability: the `api.js` envelope parser plus a timeout; the `useApi` hook ignores stale responses; the `arr`, `num` and `str` helpers guard every field; and a route-level `ErrorBoundary` resets on navigation.
- Light and dark themes via `prefers-color-scheme`.

**Testing:** see [TESTING_REPORT.md](TESTING_REPORT.md). There are 95 automated tests (all passing), including the RAG retrieval evaluation, plus manual end-to-end UI tests in demo and live Groq modes.

**Deployment:** see [DEPLOYMENT.md](DEPLOYMENT.md). This covers what Vercel needs (entrypoint, dependencies, frontend build, environment variables), the serverless constraints handled in code, the pre-release checklist, and known limitations.
