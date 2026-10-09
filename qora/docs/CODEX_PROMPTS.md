# QORA — Codex Prompt Pack v1.0

> Copy-paste prompts for a coding agent (Codex / Claude Code / similar). Each prompt assumes the
> repo state produced by the previous prompts. Run them **in order**. Every prompt embeds the
> constraints an agent needs so it cannot drift from the architecture.
>
> **Global preamble (append to every prompt):**
>
> *You are implementing QORA, a Modular Monolith (FastAPI + SQLAlchemy 2.0 + Pydantic v2 +
> PostgreSQL). Read `qora/docs/ARCHITECTURE.md`, `qora/docs/ERD.md`, `qora/docs/API_CONTRACT.md`
> and `qora/docs/PHASING.md` first. Modules live in `backend/app/modules/<name>/` with
> `router.py, service.py, repository.py, schemas.py, models.py`. Modules communicate only via
> service interfaces or the HTTP contract — never by importing another module's internals.
> Python 3.11+, typed code, tests required. Tag PRD requirements as `[PRD]` in docstrings where relevant.*

---

## Phase 0 prompts

### P0-1 · Monorepo & module skeleton
> Create the backend skeleton for the QORA modular monolith: `backend/app/modules/` with the 15
> modules from ARCHITECTURE §2 (identity, profile, personal_qora, conversation, intent, service,
> creator, runtime, knowledge, permission, outcome, qualification, reputation, analytics, reward).
> Each module gets empty but importable `router.py / service.py / repository.py / schemas.py /
> models.py` plus `__init__.py` exporting a `ModuleRouter`. Create `backend/app/main.py`
> registering all routers under `/api/v1`, the error-envelope exception handlers from
> API_CONTRACT §0, request-id middleware (`trace_id`), and a `/api/health` endpoint. Add
> `alembic.ini` + first migration creating an empty schema, `pyproject.toml` with pinned deps
> (fastapi, sqlalchemy>=2, pydantic>=2, alembic, psycopg, redis, structlog, pytest, httpx),
> and Docker Compose (api, postgres:16, redis:7). Include a boundary test that fails if a
> module imports another module's `models` or `repository`.

### P0-2 · Identity & Auth
> Implement the identity module per ERD §1 (USERS, SESSIONS, DEVICES) and API_CONTRACT §1.
> Email+password (argon2id) with rotating refresh tokens bound to devices; OIDC-ready
> `auth_provider` column. Endpoints: register, login, refresh, logout, sessions list/revoke,
> `GET /me`, `PATCH /me/account`. One user may be consumer AND creator simultaneously `[PRD]` —
> do not create separate accounts. Add pytest coverage: happy paths, token rotation, revoked
> session rejection, duplicate email 409.

### P0-3 · Profiles with privacy boundary
> Implement the profile module per ERD §1 (PRIVATE_PROFILES, CREATOR_PROFILES, BUSINESS_PROFILES)
> and API_CONTRACT §2. The public creator projection may only return `display_name, bio,
> headline, expertise_tags, verification_status, trust_score, published_at` — write an explicit
> serializer for it and a contract test asserting private fields (language, timezone, birth_date,
> preferences, memories) can never appear in any public response `[PRD]`.

---

## Phase 1 prompts

### P1-1 · Personal QORA: memory, goals, journeys
> Implement personal_qora per ERD §2 and API_CONTRACT §3 (memories with the 7 kinds + metadata
> fields source/confidence/sensitivity/share_policy/expiry, goals, journeys lite). Include
> `resolve_context(user, purpose)` in the service layer returning the minimal context set for a
> given purpose (least-context privilege `[PRD]`). Right-to-forget: `DELETE /me/memories/{id}`
> must also purge derived cache entries. Tests for expiry and sensitivity filtering.

### P1-2 · Permission engine
> Implement the permission module per ERD §2 CONTEXT_GRANTS and API_CONTRACT §10. Modes:
> ALLOW_ONCE (consumed on first use), ALWAYS_ALLOW, DENY. Provide `permission.resolve()`,
> `permission.consume_once()` and an audit trail endpoint. The runtime must call resolve BEFORE
> any context reaches a service `[PRD — hard rule]`. Contract test: a service request without a
> grant receives only public context.

### P1-3 · Intent engine v1
> Implement intent per ERD §4 and API_CONTRACT §5. Pipeline: intent detection → decomposition →
> entity extraction → ambiguity detection → capability mapping. Hybrid: LLM call behind the
> Model Gateway + deterministic fallback rules so the system degrades gracefully. Persist
> INTENTS, INTENT_ENTITIES, CAPABILITIES and USER_INTENT_HISTORY. Output shape exactly as
> API_CONTRACT §4 `intent` block. Include a fixture suite of 30 labeled user utterances
> (EN) asserting primary_intent and required_capabilities.

### P1-4 · Service registry & versions
> Implement service per ERD §5 (SERVICES, SERVICE_VERSIONS, LIFECYCLE_TRANSITIONS) and
> API_CONTRACT §6. A Service is a first-class entity `[PRD]` with purpose, audience, risk_level,
> visibility, outcome_definition on each version. Implement the lifecycle state machine from
> ARCHITECTURE §4.10 (reject invalid transitions with 409 + allowed actions). Version pinning:
> sessions always reference an exact `service_version_id`.

### P1-5 · Model Gateway
> Implement runtime/model_gateway with a provider-agnostic interface
> (`invoke(needs, messages, tools) → result`): at least two adapters (OpenAI-compatible +
> Anthropic-compatible) behind capability routing (reasoning, structured_output, tool_calling,
> long_context) with cost/latency/policy selection `[TECH]`. No service module may import a
> provider SDK — enforce with the boundary test. Record MODEL_CALLS (tokens, latency, cost).

### P1-6 · Service runtime v1 + failure recovery
> Implement the runtime pipeline per ARCHITECTURE §4.11: load version → policy → context
> resolve → permission check → knowledge (stub) → tools (stub) → model call → guardrails →
> response → outcome evaluation hook. Implement the failure taxonomy and recovery options from
> ARCHITECTURE §4.28 (`continue_with_qora | try_another_service | retry | stop`) persisted as
> FAILURE_EVENTS, surfaced in the message response `recovery` block.

### P1-7 · Conversation loop (the centerpiece)
> Implement conversation per ERD §3 and API_CONTRACT §4. `POST /conversations/{id}/messages` runs
> the full sequence in API_CONTRACT §16.1 and stores a complete INVOCATION_TRACE (candidates,
> chosen version, context shared, model/tool calls, outcome). Responses include `trace_id`.
> Integration test: the demo script from PHASING Phase 1 exit criteria, end to end, with a fake
> model adapter.

### P1-8 · Discovery + follow
> Implement discovery (`GET /services`) with intent/capability/FTS retrieval, eligibility
> filtering, ranking (configurable signal weights per API_CONTRACT §6 sample) and
> diversification. Follow = personal-fit boost `[PRD]`, not notifications. Persist
> SERVICE_INTENT_MAP / SERVICE_CAPABILITY_MAP relevance. Seed script for the intent graph.

### P1-9 · Outcome engine v1
> Implement outcome per ERD §6 and API_CONTRACT §11: each ServiceVersion carries
> `outcome_definition`; sessions evaluate to SUCCESS/PARTIAL/FAILED/UNKNOWN with composite
> signals; user confirmation endpoint collects structured feedback (not just a like `[TECH]`).

### P1-10 · Consumer frontend (chat-first)
> Using the existing React app (keep design language), build the Phase 1 consumer surface:
> conversation list + chat view with rich content blocks, service suggestion cards, permission
> modals (ALLOW_ONCE / ALWAYS_ALLOW / DENY), outcome confirmation, recovery choice UI, and a
> "My QORA" page rendering memories/goals/journeys with edit/delete. All calls go through the
> existing typed API client to `/api/v1`.

---

## Phase 2 prompts

### P2-1 · Creator interview engine
> Implement creator/interview per API_CONTRACT §7: conversation-style gap-detecting questions
> (audience, budget/method, negative boundaries, success definition) — never a long form `[PRD]`.
> Persist interview state; after answers, `generate` produces a draft ServiceSpecification
> (purpose, audience, intents, capabilities, method, behavior, knowledge needs, boundaries,
> outcome definition, examples, risk classification). Creator only reviews truth + key fixes.

### P2-2 · Simulation engine
> Implement simulation per ERD §7: auto-generate scenario cases (normal, ambiguous, edge,
> boundary, unsafe, unsupported, adversarial) from the spec; run them async (background jobs);
> store TestCase/ExpectedBehavior/ActualBehavior/Evaluation/Score/FailureReason. Surface
> per-case results and an aggregate score in the creator UI.

### P2-3 · Qualification + duplicate detection
> Implement qualification per ERD §7 / ARCHITECTURE §4.22 (six criteria → READY_TO_PUBLISH |
> NEEDS_IMPROVEMENT | RESTRICTED). Duplicate detection compares intent/capability/outcome
> embeddings (pgvector) and returns a differentiation QUESTION, not a rejection
> (ARCHITECTURE §4.23). Wire lifecycle transitions qualification_pending → ready/improve/restricted.

### P2-4 · Knowledge pipeline
> Implement knowledge per ERD §5 and API_CONTRACT §8: upload → safety scan → extraction →
> normalization → chunking → metadata → embedding → index; KnowledgeVersions bound to
> ServiceVersions. Freshness fields (source_date, last_verified_at, expires_at,
> freshness_policy) recorded `[PRD]`. The creator UI text must never say "RAG" `[PRD]` —
> "Add my training material".

### P2-5 · Creator console UI
> Build the creator flow UI matching the PRD flow Intent → Interview → Generate → Simulate →
> Review → Visibility → Qualify, with simulation scorecards and the knowledge upload page.

---

## Phase 3 prompts

### P3-1 · Trust + reputation engines
> Implement ERD §8: TRUST_SCORES with separate creator/service subjects and component scores;
> REPUTATION_EVENTS (7 kinds) applying configurable deltas; aggregation jobs. Safety failures
> must drop trust immediately; stale knowledge applies decay `[PRD]`.

### P3-2 · Ranking v2 + risk classification
> Wire all eight ranking signals (API_CONTRACT §6) with runtime-configurable weights; apply
> eligibility rules from risk_level (LOW/MEDIUM/HIGH/RESTRICTED) incl. risk-based verification
> gates `[PRD]`. Admin config endpoint for weights. Regression suite for ranking stability.

### P3-3 · Tools + guardrails
> Implement the tool system per ARCHITECTURE §4.15: registry, input/output JSON schemas,
> policy-gated execution (LLM never has unrestricted access `[TECH]`), result validation,
> timeouts, TOOL_INVOCATIONS audit. Guardrails module: policy block + output checks →
> POLICY_BLOCK failure type.

### P3-4 · Multi-service orchestration + recovery
> Decompose coordinated goals into a bounded previewable chain (max four services); pass only
> prior safe results between steps; never copy a user's context grant from one service to another.
> Add idempotent plan execution, failure stop/skip semantics, model → alternate service → direct
> QORA recovery, and ownership tests. A policy block must never be routed around.

---

## Phase 4 prompts

### P4-1 · Event pipeline + creator metrics
> Implement analytics per ERD §8: SESSION_EVENTS → daily aggregation → CREATOR_METRICS
> (users, successful sessions, returned, useful, unmet_request_count). API_CONTRACT §14
> endpoints + dashboard UI.

### P4-2 · AI creator insights
> Cluster unmet requests from session signals; detect recurring gaps; generate insight reports
> ("N users asked for X") with evidence and suggested service updates; insight inbox UI.

### P4-3 · Evaluation harness
> Add deterministic regression sets for intent routing and composite outcome status; expose a
> network-free CLI and assert suite accuracy in tests. Keep creator feedback anonymized and do
> not surface internal implementation vocabulary.

---

## Phase 5 prompts

### P5-1 · Reward engine + off-chain ledger
> Implement reward per ERD §9: RewardEvent (from outcome events only — never messages/views/
> likes `[PRD]`) → eligibility → anti-abuse → calculation → double-entry RewardLedgerEntry rows
> (system mint account). Idempotency keys on events AND entries; append-only (corrections are
> compensating rows); frozen_units for abuse review. API_CONTRACT §15 + balance/ledger UI.

### P5-2 · Hardening + scale prep
> Load tests on the message loop; cost dashboards per service; OpenSearch/vector-DB extraction
> spikes only if metrics demand; k8s manifests behind the same Docker images; settlement
> adapter interface (no chain code).

---

## Prompt hygiene checklist

- [ ] Prompt references the four docs and the global preamble.
- [ ] States the module boundaries rule and the boundary test.
- [ ] Names the exact ERD entities and API endpoints to implement.
- [ ] Defines acceptance tests (list them).
- [ ] Marks `[PRD]` vs `[TECH]` decisions where ambiguity is dangerous.
- [ ] Ends with: *"Run `pytest`, `ruff`, `mypy` and update `qora/docs/API_CONTRACT.md` if the
      contract changed. Do not modify other modules."*
