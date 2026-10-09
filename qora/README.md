# QORA — Consumer AI Service Network (Platform)

**Phase 0 + Phase 1 implemented** — the MVP loop from the architecture docs is live:

> message → **intent** → **personal context** → **service match** → **permission** →
> **service runtime** → **outcome** → **trust/reputation + rewards** → response (+ full trace)

**Backend:** Python · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · JWT (access+refresh) · bcrypt
**Frontend:** React 18 · TypeScript · Vite · Tailwind v4 · React Router
**Layout:** *Modular Monolith* — 15 domain modules with enforced boundaries (CI test).

---

## Quick start

```bash
# backend (port 8000)
cd qora/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# API docs → http://localhost:8000/api/docs

# frontend (port 5173, proxies /api → :8000)
cd qora/frontend
npm install && npm run dev
```

Or with Docker: `docker compose up` (api + web + postgres + redis).

### Demo logins

| Role | Email | Password |
|---|---|---|
| Consumer | `emma@qora.ai` | `consumer123` |
| Creator | `sarah@qora.ai` | `provider123` |
| Admin | `admin@qora.ai` | `admin123` |

**Demo script (Phase-1 exit criteria):** log in as Emma → chat
*"Next week I have an English interview for a Product Manager position"* →
QORA shows a structured intent → picks the followed **Interview Coach** → asks a
**career-context permission** (Allow once / Always / Deny) → runs the mock interview →
asks for **outcome confirmation** → saves a goal memory + journey. See it all on
**My QORA**. Full trace: `GET /api/v1/conversations/{id}/trace/{trace_id}`.

## What's implemented (vs the blueprint)

| Module | State |
|---|---|
| identity · profile (private/public split `[PRD]`) | ✅ Phase 0 |
| personal_qora (7 memory kinds, goals, journeys, least-context) | ✅ Phase 1 |
| permission (ALLOW_ONCE / ALWAYS_ALLOW / DENY + audit) | ✅ Phase 1 |
| intent (detection, decomposition, entities, ambiguity, capabilities) | ✅ v1 hybrid |
| service (registry, versions, lifecycle, discovery ranking, follow) | ✅ Phase 1 |
| runtime (model gateway, pipeline, guardrails, failure taxonomy + recovery) | ✅ Phase 1 |
| conversation (traces, orchestration, recovery UX) | ✅ Phase 1 |
| outcome (composite signals, structured confirmation) | ✅ v1 |
| reputation (event-driven trust, creator/service split) | ✅ v1 |
| reward (off-chain double-entry ledger, outcome-based `[PRD]`) | ✅ v1 |
| knowledge · creator · qualification · analytics | 🔜 Phase 2–4 skeletons |

## Tests

```bash
cd qora/backend && python -m pytest tests/ -q     # 12 tests: auth, privacy boundary,
                                                  # permissions, MVP loop, module boundaries
```

## Docs

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — Technical Architecture & Blueprint (`[PRD]` vs `[TECH]` tags)
- [`docs/ERD.md`](./docs/ERD.md) — 9 clusters, ~45 entities
- [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md) — `/api/v1` contract + normative flows
- [`docs/PHASING.md`](./docs/PHASING.md) — phases 0–5 with exit criteria
- [`docs/CODEX_PROMPTS.md`](./docs/CODEX_PROMPTS.md) — implementation prompt pack

## Repository layout

```
qora/
├── backend/        ← Platform (modular monolith) — app/modules/{15 domains}
├── frontend/       ← Phase-1 consumer app (chat-first: permission modals, outcome confirm)
├── docs/           ← architecture pipeline
├── prototype/      ← marketplace prototype v0.3 (legacy reference)
└── docker-compose.yml
```
