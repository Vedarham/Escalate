# Escalate: Testing Report

**Date:** 2026-10-24 · **Backend:** Python 3.12.7, FastAPI 0.162, Pydantic 2.14 · **Frontend:** React 19.3, Vite 8.3 · **Live AI:** Groq (`qwen/qwen3.8-27b`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`)

## 1. Automated tests (`backend/tests`): 95 / 95 passing

| File | Tests | Scope |
|---|---|---|
| `test_api.py` | 37 | functional, contract and edge-case tests for the construction modules |
| `test_ai_layer.py` | 17 | LLM gateway, schema enforcement, provider fallback, CPM |
| `test_legal.py` | 41 | legal agent: knowledge-base integrity, RAG retrieval evaluation, citation verification, API edge cases |

The tests run fully offline: demo mode, an isolated temporary SQLite store, mocked LLM providers and mocked weather.

### Functional and contract tests (`test_api.py`)
| ID | Test | Expected | Result |
|---|---|---|---|
| F-01 | Health endpoint | `status: ok`, mode reported | ✅ |
| F-02 | Safety analysis with a valid photo | 200; data validates as `SafetyReport`; score 0–100 | ✅ |
| F-03 | Crack analysis with element/material/age | 200; `CrackReport`; structural concern ⇒ engineer flag | ✅ |
| F-04 | Valuation (data only) | 200; low ≤ mid ≤ high; price/sqft = mid ÷ area | ✅ |
| F-05 | Valuation with photo | `image_observations` populated | ✅ |
| F-06 | Planning estimate | costs add up to total; every dependency finishes before its successor starts; total = max end day | ✅ |
| F-07 | Premium vs standard tier | premium total > standard total | ✅ |
| F-08 | Daily advisory, heavy rain | concrete pour → `postpone`; alerts present | ✅ |
| F-09 | Weather alert rules (wind 55 km/h, 41 °C) | wind and heat alerts raised | ✅ |
| F-10 | Knowledge chat | 200; `KnowledgeAnswer` | ✅ |
| F-11 | Chat with history and an image | 200 | ✅ |
| F-12 | History round trip | record listed and retrievable; image served as `image/jpeg` | ✅ |

### Edge-case and negative tests
| ID | Scenario | Expected | Result |
|---|---|---|---|
| E-01 | Missing image on an image module | 422 `image_required` | ✅ |
| E-02 | Text file uploaded as an image | 422 `unsupported_image` | ✅ |
| E-03 | Empty (0-byte) image | 422 `empty_image` | ✅ |
| E-04 | **Incomplete image** (JPEG truncated to ⅓) | 422 `corrupted_image` | ✅ |
| E-05 | Tiny image (20×20) | 422 `image_too_small` | ✅ |
| E-06 | Image over the size limit | 413 `image_too_large` | ✅ |
| E-07 | Very dark photo | 200, plus a "very dark" warning in `meta.warnings` | ✅ |
| E-08 | PNG and WEBP formats | accepted | ✅ |
| E-09 | Negative building age | 422 `invalid_input` | ✅ |
| E-10 | Valuation with negative area, unknown type, missing location, or extra field | 422 `invalid_payload` with field details | ✅ |
| E-11 | Malformed JSON payload or missing payload | 422 `invalid_payload` / `missing_payload` | ✅ |
| E-12 | Planning with 0 floors, 0 area, or unsupported currency | 422 `invalid_input` | ✅ |
| E-13 | Weather service unavailable | 200, advisory still produced, with a warning | ✅ |
| E-14 | Chat: empty list, last message from assistant, empty content, injected `system` role | 422 `invalid_payload` | ✅ |
| E-15 | Unknown route, wrong method, missing record, path traversal on `/uploads` | JSON 404 / 405 errors (never HTML) | ✅ |

### AI-layer tests (`test_ai_layer.py`, mocked providers)
| ID | Scenario | Expected | Result |
|---|---|---|---|
| A-01 | Normal live call | strict `json_schema` response_format sent; text model used | ✅ |
| A-02 | Image attached | vision model used; base64 data URL in the message | ✅ |
| A-03 | Output wrapped in `<think>` and a ```json fence | parsed correctly | ✅ |
| A-04 | First output invalid against the schema | repair prompt sent; second output accepted | ✅ |
| A-05 | Provider rejects `json_schema` (400) | degrades to `json_object` | ✅ |
| A-06 | Groq rate-limited (429) | falls back to Hugging Face, with a warning | ✅ |
| A-07 | Groq out of credits (402) | falls back to Hugging Face | ✅ |
| A-08 | Every provider out of credits | `AIServiceError` stating "no remaining credits" for each | ✅ |
| A-09 | Every provider fails (500, then invalid JSON twice) | `ai_unavailable` with 2 failure details | ✅ |
| A-10 | `FALLBACK_TO_DEMO=true` with all providers down | demo data with an "unavailable" warning | ✅ |
| A-11 | AI error during a request | HTTP 502 JSON envelope | ✅ |
| A-12 | Messy output (`"HIGH"`, score 140, confidence 85, string instead of list) | normalised to `high`, 100, 0.85, `[...]` | ✅ |
| A-13 | Unordered value range | sorted to low ≤ mid ≤ high | ✅ |
| A-14 | Strict schema generation | no `$ref`/`$defs`; all properties required; `additionalProperties: false` | ✅ |
| A-15 | CPM on a known graph | total 17 days; critical path A→C→D; slack task not critical | ✅ |
| A-16 | AI graph with a cycle, unknown dependency and duplicate ID | repaired, with 3 warnings; schedule still produced | ✅ |

### Land legal advisor tests (`test_legal.py`)
| ID | Scenario | Expected | Result |
|---|---|---|---|
| L-01 | Knowledge-base integrity (58 articles) | unique, well-formed IDs; every article has a body, sources and valid jurisdictions | ✅ |
| L-02 | Tokenizer on legal terms ("Satbara (7/12) and EC for a GPA sale") | expands to 7/12, encumbrance certificate, power of attorney | ✅ |
| L-03 | **RAG retrieval evaluation**: 25 realistic buyer questions (GPA sale, NRI farmland, daughters' rights, adverse possession, B-khata, TDS, lal dora, patta mismatch, gairan land, lis pendens, new-tenure land, MP khasra/B-1, MP tribal land, MP diversion…) | expected article in the top 5 | ✅ 25/25 (recall@5 = 100%) |
| L-04 | State boost | the same query ranks Maharashtra records first for `maharashtra` and Karnataka records first for `karnataka` | ✅ |
| L-05 | Off-topic query ("who will win the cricket world cup") | no passages retrieved ("will" as a verb is not treated as a testament) | ✅ |
| L-06 | Agent contract and grounding (GPA question) | `LegalAdvice` validates; cites TX-04; every citation ⊆ retrieved passages; `cited` flags consistent | ✅ |
| L-07 | Document photo attached | 200 with sources | ✅ |
| L-08 | Multi-turn conversation | 200 | ✅ |
| L-09 | Invalid payloads: empty messages, assistant last, unknown state, unknown buyer type, extra field | 422 `invalid_payload` | ✅ |
| L-10 | Knowledge-base endpoints | article list; TX-04 full text; unknown ID → 404 | ✅ |
| L-11 | History filter `module=legal` | only legal records | ✅ |
| L-12 | **Fabricated citations** (model cites ZZ-99 and inline [QQ-01]) | removed, with a warning; valid [TX-04] kept; planner clarifications merged; planner ran on the fast model | ✅ |
| L-13 | Model returns no citations | falls back to the top retrieved passages | ✅ |

## 2. End-to-end and UI stability tests (manual, in-app browser)

| ID | Flow | Mode | Result |
|---|---|---|---|
| U-01 | Dashboard loads, health badge, module cards, recent activity | demo + live | ✅ |
| U-02 | Safety: upload → analyse → score ring, hazards, PPE table, actions, JSON toggle | demo + live | ✅ (live: unprotected worker at height → critical, score 15) |
| U-03 | Crack: upload → analyse → severity badges, cracks, causes, actions | live | ✅ (diagonal crack at opening → severe, structural, engineer required) |
| U-04 | Valuation: form → value hero, drivers bar chart | demo + live | ✅ (₹1.67 Cr for a 1,450 sqft 3BHK in Whitefield) |
| U-05 | Valuation: 1-character location (server-side validation) | demo | ✅ error banner shows field details |
| U-06 | Planning: costs, materials table, Gantt with critical path, concept and SVG floor plan | demo + live | ✅ |
| U-07 | Site assistant: live Open-Meteo forecast, alerts, per-activity advice | demo + live | ✅ (Chennai rain → slab pour postponed) |
| U-08 | Knowledge chat: suggestion chip → markdown answer, key points, code refs, follow-up chips | demo + live | ✅ |
| U-09 | History: filter, open record, view stored image and JSON | demo | ✅ |
| U-10 | Mobile layout (375 px): slide-in navigation, single-column forms | demo | ✅ |
| U-11 | Production build served by FastAPI on :8000 (SPA routes and `/api` together) | live | ✅ |
| U-12 | Legal advisor: profile → suggestion → risk badge, grounded answer, citation chips, red flags, documents table | live | ✅ |
| U-13 | Legal advisor: click a citation chip → full source article (statutes and body) | live | ✅ |

### Defects found and fixed during testing
| # | Defect | Fix |
|---|---|---|
| D-1 | Chat page crashed in Chromium: `scrollIntoView()` returns a Promise there, which was returned from `useEffect` | Effect body wrapped in braces; the error boundary contained the crash |
| D-2 | Valuation form converted empty *text* fields to `0` → 422 on `notes` | Only numeric fields are coerced |
| D-3 | HTTP 402 "no credits" from Hugging Face raised an unhandled 500 | Generic `APIStatusError` / `APIError` now handled → fallback or clean 502 |
| D-4 | Unknown `/api/*` routes returned the SPA HTML once `dist/` existed | Frontend served with `app.frontend(fallback="index.html")`, which applies only to HTML navigation; API misses return a JSON 404 |
| D-5 | Live AI schedules were unrealistically short (110 days for 6,000 sqft, 4 floors, premium) | Duration benchmark added to the prompt plus a deviation warning → 345 days (benchmark ≈ 324) |
| D-6 | Long AI text squeezed the crack table and Gantt labels | Crack table changed to cards; responsive Gantt label column |
| D-7 | Legal agent hit Groq's free-tier tokens-per-minute limit (429) on the third consecutive question | Planner moved to `openai/gpt-oss-20b` (separate quota); client retries 429 responses honouring `retry-after` |
| D-8 | Retrieval matched "who **will** win…" to articles about wills (testaments) | "will" is ignored as a verb and mapped to *testament* only after a determiner ("a will", "without a will") |

## 3. Live AI output validation (Groq)

| Endpoint | Model | Latency | Schema-valid on 1st attempt |
|---|---|---|---|
| `/api/assistant/chat` | openai/gpt-oss-120b | 2.5 s | ✅ |
| `/api/cracks/analyze` | qwen/qwen3.8-27b | 1.4 s | ✅ |
| `/api/safety/analyze` | qwen/qwen3.8-27b | 2.0 s | ✅ |
| `/api/planning/estimate` | openai/gpt-oss-120b | 5.8 s | ✅ |
| `/api/assistant/daily`, `/api/valuation/estimate` | openai/gpt-oss-120b | not measured (run via UI) | ✅ |
| `/api/legal/ask` (planner + answer) | gpt-oss-20b + gpt-oss-120b | 4.6–6.3 s | ✅ |

### Live legal-advisor checks
| Question | Risk | Cited | Observation |
|---|---|---|---|
| Non-farmer software engineer offered Maharashtra farmland, 50% cash before 7/12 transfer | high | LR-01, ST-MH-01/02, TX-06, LR-02 | Flags the s.63 agriculturist restriction, cash risk and missing NA conversion ✅ |
| Grandfather died intestate; uncle sold the house without the daughter's signature | high | FS-01, FS-02, FS-03 | Explains daughters' coparcenary rights (2005 amendment) ✅ |
| NRI wants a "farmhouse plot" near Bengaluru | high | LR-07, LR-02, TX-07 | FEMA bar on farm houses and agricultural land; conversion check; TDS ✅ |
| Seller has a bank loan on the land | high | DF-03, TT-06, TX-08 | Pay the bank directly against a closure letter and release; CERSAI ✅ |
| "Who will win the cricket world cup?" | — | none | `in_scope: false`, politely declined ✅ |
| Madhya Pradesh: farmhouse near Indore on undiverted land held by a government patta holder | high | ST-MP-01, ST-MP-02 | Flags the Collector-permission requirement, the missing s.172 diversion and B-1 / khasra checks ✅ |

Live test images were synthetic drawings, not real site photos. The models said so themselves ("stylized illustration") and lowered their confidence, which is the intended behaviour. Accuracy should be re-validated on real site photographs before production use.
