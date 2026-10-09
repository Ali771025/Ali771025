# QORA — Development Phasing Plan v1.0

> The MVP proves one loop **[PRD]**: **Consumer + Creator + Useful Outcome**.
> Phases are ordered so that each one ends with a demoable, testable increment.
> Estimated sprints assume 1–2 full-stack engineers + AI support tooling (2-week sprints).

---

## Phase 0 — Platform Foundation *(≈ 1–2 sprints)*

**Goal:** skeleton that every later module plugs into without rework.

| Deliverable | Detail |
|---|---|
| Monorepo layout | `backend/` (modular monolith per ARCHITECTURE §2), `frontend/`, `infra/`, `docs/` |
| Module skeleton | all 15 modules created with router/service/repository/schemas + boundary lint (no cross-module imports except contracts) |
| PostgreSQL + Alembic | migrations pipeline, seed framework |
| Auth | register/login/refresh, OIDC-ready, sessions & devices |
| Profiles | private profile + optional creator profile, strict public projection |
| Observability | structured logging, trace_id everywhere, OpenTelemetry stubs, Sentry-compatible hook |
| DevOps | Docker Compose (api, db, redis, mailhog), CI (lint, type-check, tests, build) |
| Contract tests | error envelope, pagination, idempotency middleware |

**Exit criteria:** `docker compose up` boots API + frontend shell; CI green; a user can
register, log in, edit private profile, and no private field appears in any public response.

---

## Phase 1 — The MVP Loop *(≈ 3–4 sprints)*

**Goal:** a user says something → QORA understands → a service runs → a useful outcome is produced.

| Deliverable | Detail |
|---|---|
| Conversation core | conversations, messages, invocation traces (full trace per request) |
| Personal QORA v1 | memory classes (profile fact, preference, goal, temporary context), goals, journeys lite |
| Permission UX | ContextGrant with ALLOW_ONCE / ALWAYS_ALLOW / DENY; least-context resolver |
| Intent Engine v1 | detection, decomposition, entities, ambiguity flag, capability mapping (LLM + rules hybrid) |
| Service Registry v1 | services + versions + lifecycle (draft → published subset) |
| Service Runtime v1 | pipeline per ARCHITECTURE §4.11, guardrails basic, failure taxonomy + recovery UX |
| Model Gateway v1 | 2+ providers behind capability routing (cost/latency/policy) |
| Discovery v1 | intent + capability search (Postgres FTS), configurable ranking signals (first weights) |
| Outcome Engine v1 | outcome_definition per version, session → SUCCESS/PARTIAL/FAILED/UNKNOWN, user confirmation |
| Follow | follow = personal-fit boost in matching |
| Frontend | chat-first consumer app, permission modals, outcome confirmation, recovery choices |

**Exit criteria (demo script):** *“Next week I have an English interview for a PM position”* →
structured intent shown in trace → Interview Coach service selected (followed service boosts fit) →
career context permission requested → mock interview runs → deliverable + outcome SUCCESS →
memory saved (goal + temporary context) → journey can be continued next day.

**Explicitly out of scope:** creator interview flow (Phase 2), rewards (Phase 5), RAG uploads (Phase 3).

---

## Phase 2 — Creator Platform & Qualification *(≈ 3–4 sprints)*

**Goal:** a creator publishes a real no-code AI service using only conversation.

| Deliverable | Detail |
|---|---|
| Interview Engine | gap-detecting question flow, conversation over configuration |
| Spec Generator | draft ServiceSpecification (purpose, audience, boundaries, outcome, risk) + truth review |
| Simulation Engine | 7 scenario kinds, TestCase/Expected/Score/FailureReason records (async jobs) |
| Qualification Engine | 6 PRD criteria + result READY_TO_PUBLISH / NEEDS_IMPROVEMENT / RESTRICTED |
| Duplicate Detection | intent/capability/outcome embeddings, "what makes you different?" UX |
| Lifecycle complete | full state machine incl. UNLISTED, REQUALIFICATION, rollback |
| Knowledge v1 | upload → scan → extract → chunk → embed (pgvector) → collection → version binding |
| Creator analytics v1 | users, successful sessions, returned, useful |

**Exit criteria:** a non-technical creator goes from intent statement to a qualified, published
service with knowledge attached, without seeing the words prompt/RAG/model.

---

## Phase 3 — Trust, Outcome Depth & Reliability *(implemented in the QORA prototype; ≈ 2–3 sprints)*

**Goal:** outcomes and trust become measurable and ranking becomes honest.

| Deliverable | Detail |
|---|---|
| Outcome scoring v2 | composite signals (service + completion + structured + confirmation + follow-up behavior) |
| Trust Engine | separate creator trust / service trust with component scores |
| Reputation Engine | event-driven deltas (7 event kinds), no single-number storage |
| Risk classification | LOW/MEDIUM/HIGH/RESTRICTED with risk-based verification gates |
| Ranking v2 | all 8 PRD signals live, weights configurable via admin config |
| Failure recovery v2 | fallback model → fallback service → direct QORA, per failure type |
| Tools v1 | tool registry, policy-gated execution, result validation |
| Freshness | stale knowledge detection affecting trust + ranking |
| Multi-service orchestration | previewable intent plan, bounded sequential chain, result handoff, owner isolation; context is never reused across services |

**Exit criteria:** stale or unsafe services visibly drop in Explore; a service with bad outcomes
loses rank within one aggregation cycle; tool calls are impossible outside policy.

---

## Phase 4 — AI Insights & Analytics *(implemented in the QORA prototype; ≈ 2 sprints)*

| Deliverable | Detail |
|---|---|
| Event pipeline | session events + structured outcomes → idempotent daily aggregation → creator metrics (daily buckets); refreshed after session/feedback events |
| AI Creator Insights | cluster anonymized unmet requests → recurring gap → evidence-backed report + suggested update |
| Analytics dashboards | cross-service overview, daily activity, insight inbox with dismiss/acted-on states |
| Evaluation harness | offline regression suites for intent matching and outcome evaluators (`backend/scripts/run_evaluation.py`) |

**Exit criteria:** the insight *"N users asked for X"* is generated automatically from real sessions.

**Prototype implementation note [TECH]:** aggregation currently runs through FastAPI background-task adapters and a daily CLI (`backend/scripts/run_daily_analytics.py`); the task functions are designed to move behind a queue without changing contracts. Request clustering is deterministic and only uses sanitized, explicit outcome feedback. No internal AI infrastructure vocabulary is exposed in the creator interface.

---

## Phase 5 — Reward Economy & Scale *(≈ 2–3 sprints)*

| Deliverable | Detail |
|---|---|
| Reward Engine | events → eligibility → anti-abuse → calculation |
| Off-chain Ledger | double-entry, append-only, idempotent (ERD §9) |
| Reward UX | balance, ledger, earning rules |
| Anti-abuse | freeze/reversal workflow, velocity caps |
| Scale prep | OpenSearch (if needed), vector DB extraction (if needed), k8s manifests (only if real need) |
| Settlement adapter | interface only — chain settlement stays future |

**Exit criteria:** successful outcomes mint rewards exactly once (idempotency proven by tests);
ledger reconciles; abuse scenario freezes and reverses correctly.

---

## Mapping: existing `qora/` prototype → phases

The current code (marketplace-style v1) is a **valid scaffold**, not the final product:

| Existing asset | Reuse in |
|---|---|
| `backend/app/core` (config, JWT, bcrypt) | Phase 0 identity |
| `backend/app/db` + SQLAlchemy models style | Phase 0+ everywhere |
| Services/categories CRUD + search | Phase 1 Service Registry + Discovery (rename, extend) |
| Orders + wallet + transactions | Phase 5 Reward Ledger precursor (double-entry upgrade) |
| Reviews | Phase 1/3 outcome confirmation signals |
| Assistant endpoint (rule matcher) | Phase 1 Intent Engine v1 skeleton |
| React app: auth context, API client, layout | Phase 0 frontend shell |
| Chat page UI | Phase 1 conversation UI base |
| Provider/admin pages | Phase 2 creator console + Phase 0 admin lite |

Recommended: **keep the prototype running** as `qora/backend` + `qora/frontend` while building
Phase 0+ modules in the same repo behind `/api/v1`, and cut over when Phase 1 exit criteria pass.

---

## Risk register (top 5)

| Risk | Mitigation |
|---|---|
| Intent quality too low for good matching | LLM+rules hybrid; confidence + ambiguity UX; human-fixable intent history |
| Outcome evaluation becomes "like button" | structured signals per service outcome_definition; follow-up behavior |
| Context privacy leak | permission gate enforced in runtime (not in UI), audit endpoint, contract tests |
| Provider coupling / cost blowups | Model Gateway from day one of Phase 1; per-service cost budgets |
| Over-engineering the ledger/graph | strict phase gates; pgvector+Postgres until proven insufficient |
