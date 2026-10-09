# QORA — Consumer AI Service Network

**Phases 0–4 are implemented in the prototype.** QORA joins a consumer app, personal AI, a service network, a no-code creator platform, multi-service orchestration, measurable outcomes, trust and creator analytics.

> A user describes an outcome. QORA understands the request, protects personal context, selects or coordinates specialist services, and measures whether the work helped.

## Stack

- **Backend:** Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic v2 · SQLite for local development
- **Frontend:** React 18 · TypeScript · Vite · Tailwind v4 · React Router
- **Shape:** modular monolith under `backend/app/modules/`; modules communicate through service interfaces

## Quick start

```bash
# API — http://localhost:8000/api/docs
cd qora/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Web app — http://localhost:5173
cd qora/frontend
npm install
npm run dev -- --host 0.0.0.0
```

The Vite app proxies relative `/api` requests to the API. Local database files are ignored by Git.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Consumer | `emma@qora.ai` | `consumer123` |
| Consumer | `omar@qora.ai` | `consumer123` |
| Creator | `sarah@qora.ai` | `provider123` |
| Creator | `marcus@qora.ai` | `provider123` |
| Creator | `lena@qora.ai` | `provider123` |
| Admin | `admin@qora.ai` | `admin123` |

## What's implemented

| Area | Highlights |
|---|---|
| Phase 0–1 · Platform + MVP loop | identity, private/public profile split, permissions, intent, service discovery, runtime, conversations, outcomes, rewards |
| Phase 2 · Creator platform | gap-detecting interview, service draft/review, seven-case simulation, qualification, lifecycle, training-material collections and creator console |
| Phase 3 · Orchestration + trust | multi-service preview and execution, composite outcomes, creator/service trust, seven reputation event kinds, risk-based verification, all eight ranking signals, recovery, allow-listed tools, freshness decay |
| Phase 4 · Analytics | automatic daily metric refresh, cross-service dashboard, anonymized recurring-request insights, insight inbox, offline evaluation suites |

Creator-facing language stays simple: **Training material** and **QORA handles everything else**.

## Demo flows

- **Creator:** sign in as Sarah → **Create** → describe a service → answer the interview → review → simulate → qualify → publish. Use **Training material** to attach a collection.
- **Orchestration:** sign in as Emma → **Coordinate** → ask for help preparing for an interview and editing a resume → review the plan → run its service steps.
- **Analytics:** sign in as Sarah → **Create → My services** → refresh daily results and review recurring user requests.

## Tests and regression harness

```bash
cd qora/backend
.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/run_evaluation.py
.venv/bin/python scripts/run_daily_analytics.py
```

Tests cover module boundaries, user/profile privacy, lifecycle, creator flow, tools, trust/risk gates,
ranking, orchestration, freshness recovery, daily analytics and evaluation regression cases.

## Project docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — product and technical architecture, tagged `[PRD]` / `[TECH]`
- [`docs/ERD.md`](docs/ERD.md) — current schema map
- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) — REST contract
- [`docs/PHASING.md`](docs/PHASING.md) — phase goals and acceptance criteria
- [`docs/CODEX_PROMPTS.md`](docs/CODEX_PROMPTS.md) — implementation prompts

## Current prototype limits

Database migrations, a production job queue, durable object storage and provider-backed model failover
remain deployment-hardening work. The local fallback is deterministic, tool handlers are deliberately
allow-listed, and daily aggregation can also be invoked by a scheduler through the provided CLI.
