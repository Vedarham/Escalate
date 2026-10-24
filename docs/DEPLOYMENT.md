# Escalate: Deployment Notes and Demonstration Guide

You deploy this project yourself through GitHub and Vercel. This page lists what the platform needs from the code, and what the code already handles.

## 1. What a Vercel deployment needs

| Item | Value |
|---|---|
| Python entrypoint | `backend/app/main.py`, variable `app` (FastAPI). As a module path: `backend.app.main:app`. |
| Python version | 3.12 is recommended (Vercel's default); the code runs on 3.10+ |
| Python dependencies | `backend/requirements.txt`. `pytest` is only needed for tests and can be left out of the runtime install. FastAPI 0.162 or later is required for `app.frontend()`. |
| Frontend build | `frontend/` is a Vite app. `npm run build` writes `frontend/dist`. |
| Serving the frontend | If `frontend/dist` exists when the app starts, FastAPI serves it through `app.frontend("/", fallback="index.html")`. On Vercel these files are promoted to the CDN automatically, and `/api/*` routes always take priority. |
| Alternative layout | Host `frontend/` as its own Vite project, set `VITE_API_BASE` to the API URL at build time, and add the frontend's domain to `CORS_ORIGINS`. |
| Function duration | Live AI calls usually take 2–7 s. The legal agent makes two calls, about 5–10 s, and up to ~20 s when a provider is rate-limiting. Allow at least 60 s for the Python function. |
| Bundle | Runtime dependencies are small (no ML libraries). The knowledge base (`backend/app/knowledge/`) must be included; it is read at start-up. |

**Environment variables** (Vercel project settings; never commit `.env`): `GROQ_API_KEY` (required for live AI), optionally `HF_TOKEN`, plus any of the variables listed in `backend/.env.example`. `DEMO_MODE` must be `false` or unset in production.

**Serverless constraints already handled in code**
- **Read-only filesystem:** when the `VERCEL` environment variable is present, storage automatically moves to `/tmp/escalate-storage`. History and uploaded images are therefore **ephemeral**: they last for the life of a function instance. For permanent history, replace `services/storage.py` with a hosted database (for example Postgres).
- **4.5 MB request body limit:** the browser downscales photos to at most 1600 px JPEG before upload (`compressImage` in `frontend/src/utils.js`).
- **Cold starts:** the BM25 index (58 articles) builds in milliseconds; no model weights are loaded.
- **Rate limits:** Groq's free tier limits tokens per minute for each model. The legal planner uses the separate `openai/gpt-oss-20b` quota, the client retries 429 responses (honouring `retry-after`), and Hugging Face is the automatic fallback.

**Pre-release checklist**
1. All backend tests pass (95).
2. `npm run build` succeeds.
3. `GET /api/health` returns `"mode": "live"` and the expected primary provider.
4. Each module returns a result in the UI, and **View JSON contract** shows `meta.mode = live`.
5. The legal advisor answers a sample question with citations (for example, "Is it safe to buy from a GPA holder?" → `TX-04`).

## 2. Demonstration script (about 7 minutes)
1. **Dashboard:** point out the Live badge, the providers and the seven modules.
2. **Safety:** upload a site photo, then show the score ring, critical hazards with OSHA/IS references, and the PPE table. Open **View JSON contract**.
3. **Cracks:** upload a crack photo, then show severity, structural concern, the engineer flag and repair methods.
4. **Planning:** generate a plan for 3,200 sqft, G+2, Pune, then show costs, the Gantt chart with the critical path, and the floor plan.
5. **Valuation:** estimate the value of a Whitefield apartment.
6. **Site assistant:** show the live forecast, then go / postpone per activity.
7. **Land legal advisor:** select Maharashtra and agricultural land, and ask "I am not a farmer, can I buy this land?". Show the risk badge, red flags, documents to verify, then click a citation chip to open the source article.
8. **History:** show the stored inputs and outputs for traceability.
9. **Edge case:** upload a corrupted file to show the clean error message.

## 3. Known limitations
1. **AI accuracy.** Vision models estimate crack widths and PPE status from pixels. Small or occluded hazards can be missed.
2. **Legal advisor scope.** The knowledge base covers general Indian land and property law and 9 states. It is not exhaustive, it is not updated automatically when laws change, and it is not legal advice. Rates, procedures and portals change, so verify current rules and get an advocate's title report. Questions outside the knowledge base get lower confidence and a warning.
3. **Valuation** relies on the model's general market knowledge, not live transaction data.
4. **Cost estimation** uses national-average thumb rules and indicative INR/USD rates.
5. **Schedules** are AI-drafted and checked by CPM, but they are not resource-levelled.
6. **Floor plans** are conceptual block diagrams, not to scale.
7. **Weather** geocodes by city name; ambiguous names resolve to the most populous match.
8. **One image per request**, up to 8 MB (downscaled in the browser). No video.
9. **Free-tier limits.** When every provider fails, the API returns a clear 502, or demo data if `FALLBACK_TO_DEMO=true`.
10. **No authentication.** History is shared by everyone using the instance, and is ephemeral on serverless hosts.
11. **Language.** English only.

## 4. Screenshots
[`screenshots/`](screenshots/) contains `01_dashboard`, `02_safety_monitoring`, `03_crack_analysis`, `04_valuation`, `05_planning_gantt`, `06_site_assistant_weather`, `07_land_legal_advisor` and `08_mobile_dashboard`, all captured with live Groq results in the Escalate theme. The brand logo is in [`assets/escalate-logo.png`](assets/escalate-logo.png).
