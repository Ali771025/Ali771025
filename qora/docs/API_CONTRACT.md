# QORA — API Contract v1.0

> REST/JSON contract for the MVP and near-post-MVP surface. Base path `/api/v1`.
> Follows `ARCHITECTURE.md` and the `ERD.md` entities. Every endpoint lists its owning module —
> modules may only call each other through these contracts (modular monolith rule).

---

## 0. Conventions

### Authentication **[TECH]**
- OAuth2/OIDC-compatible: `POST /auth/login` → `{access_token, refresh_token}`.
- `Authorization: Bearer <access_token>` (short-lived JWT, 15 min).
- Refresh via `POST /auth/refresh` (rotating refresh tokens, device-bound).

### Error envelope (all non-2xx)

```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "Human-readable summary",
    "details": [{"field": "context_type", "issue": "unknown value"}],
    "trace_id": "trc_01H…"
  }
}
```

Canonical codes: `VALIDATION_ERROR · UNAUTHENTICATED · FORBIDDEN · NOT_FOUND · CONFLICT ·
RATE_LIMITED · MODEL_FAILURE · TOOL_FAILURE · MISSING_CONTEXT · PERMISSION_DENIED ·
KNOWLEDGE_FAILURE · SERVICE_UNAVAILABLE · POLICY_BLOCK · TIMEOUT · LOW_CONFIDENCE`

### Pagination & conventions
- Cursor pagination: `?cursor=<opaque>&limit=20` → `{"items": [...], "next_cursor": "..."}`
- All timestamps RFC 3339 UTC. All ids UUIDs. Money/reward units are integers.
- Idempotency: mutating endpoints accept `Idempotency-Key` header.
- Rate limits are per user and per service.

---

## 1. Identity module (`identity`)

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | create user (email/phone/OIDC) |
| POST | `/auth/login` | → tokens |
| POST | `/auth/refresh` | rotate tokens |
| POST | `/auth/logout` | revoke session |
| GET | `/auth/sessions` | list active sessions/devices |
| DELETE | `/auth/sessions/{id}` | revoke a session |
| GET | `/me` | merged identity summary (id, status, profile flags) |
| PATCH | `/me/account` | email/phone/password change, account status |

```jsonc
// POST /auth/register
{ "email": "ada@example.com", "password": "•••", "display_name": "Ada",
  "roles_wanted": ["consumer", "creator"] }   // one user, multiple hats [PRD]
```

## 2. Profile module (`profile`)

| Method | Path | Description |
|---|---|---|
| GET | `/me/profile/private` | private profile (owner only) |
| PATCH | `/me/profile/private` | name, language, timezone, preferences |
| GET | `/me/profile/creator` | own creator profile |
| PATCH | `/me/profile/creator` | display name, bio, headline, expertise |
| GET | `/creators/{id}` | **public projection only** — never private fields |
| POST | `/me/profile/creator/verification` | request verification (risk-based) |

**Boundary rule:** public endpoints expose only `CREATOR_PROFILES` fields; leakage of
private fields is a contract violation *(PRD)*.

## 3. Personal QORA module (`personal_qora`)

| Method | Path | Description |
|---|---|---|
| GET | `/me/memories` | `?kind=&q=&cursor=` |
| POST | `/me/memories` | create (user-editable memories) |
| PATCH | `/me/memories/{id}` | edit / correct |
| DELETE | `/me/memories/{id}` | forget (right-to-forget) |
| GET | `/me/goals` · POST `/me/goals` · PATCH `/me/goals/{id}` | goals |
| GET | `/me/journeys` · GET `/me/journeys/{id}` | active journeys & state |
| GET | `/me/context` | QORA's current understanding (rendered) |
| POST | `/me/context/permissions` | create a `ContextGrant` |
| GET | `/me/context/permissions` | list grants |
| DELETE | `/me/context/permissions/{id}` | revoke |

```jsonc
// POST /me/context/permissions   [PRD UX: ALLOW_ONCE | ALWAYS_ALLOW | DENY]
{ "service_id": "svc_…", "context_type": "career", "scope": ["title", "years", "target_role"],
  "mode": "ALLOW_ONCE", "expires_at": null }
```

## 4. Conversation module (`conversation`) — the main loop

| Method | Path | Description |
|---|---|---|
| GET | `/conversations` | history (cursor) |
| POST | `/conversations` | open conversation (optional `journey_id`) |
| GET | `/conversations/{id}` | messages + active intent/service/journey |
| POST | `/conversations/{id}/messages` | **send message → orchestrated response** |
| GET | `/conversations/{id}/trace/{trace_id}` | full invocation trace |
| POST | `/conversations/{id}/recovery` | user choice: continue-with-QORA / try-another-service |

```jsonc
// POST /conversations/{id}/messages
{ "content": "Next week I have an English interview for a PM position",
  "content_type": "text" }
```

```jsonc
// 200 response — orchestrated result
{
  "message": { "role": "assistant", "content": "Great — let's prepare. I can run a mock interview…" },
  "intent": {
    "primary_intent": "job_interview_preparation",
    "secondary_intents": ["english_speaking_practice"],
    "entities": {"Role": "Product Manager", "Date": "next week"},
    "required_capabilities": ["interview_coaching", "english_practice"],
    "confidence": 0.94
  },
  "service_match": {
    "chosen_service_id": "svc_…",
    "candidates": [{"service_id": "svc_…", "score": 0.91}],
    "reason": "personal fit + followed service + strong outcomes"
  },
  "permission_request": {            // only when context is needed [PRD]
    "grant_id": "grt_…",
    "context_type": "career",
    "mode_options": ["ALLOW_ONCE", "ALWAYS_ALLOW", "DENY"]
  },
  "service_response": { "content": "…", "deliverable": {"kind": "itinerary|plan|review…"} },
  "outcome": { "status": "SUCCESS", "score": 0.87, "user_confirmation_required": true },
  "trace_id": "trc_…",
  "recovery": null                  // or {"failure_type": "TOOL_FAILURE", "options": [...]}
}
```

## 5. Intent module (`intent`)

| Method | Path | Description |
|---|---|---|
| POST | `/intents/analyze` | text → structured intent (exposed for debugging/UX) |
| GET | `/intents` | catalog of known intents & capabilities |
| GET | `/me/intents/history` | user intent history |

## 6. Service module (`service`) — registry & discovery

| Method | Path | Description |
|---|---|---|
| GET | `/services` | discovery: `?q=&intent=&capability=&category=&sort=` |
| GET | `/services/{id}` | public detail (version summary, trust, outcome stats) |
| GET | `/services/{id}/versions` | owner/admin: version list |
| POST | `/services` | creator: create draft |
| PATCH | `/services/{id}` | owner: update metadata |
| POST | `/services/{id}/versions` | create new version (publish flow) |
| GET | `/services/{id}/versions/{v}` | version detail |
| POST | `/services/{id}/lifecycle` | `{action: "submit_test|request_qualification|publish|pause|unlist|rollback"}` |
| POST | `/services/{id}/follow` · DELETE | follow/unfollow *(feeds personal fit)* |
| POST | `/services/{id}/save` · DELETE | save |

Discovery response (ranking internals hidden):

```jsonc
{ "items": [{
    "service_id": "svc_…", "name": "Interview Coach", "summary": "…",
    "creator": {"display_name": "…", "verification_status": "verified"},
    "outcome": {"success_rate": 0.86, "sessions": 412},
    "trust": {"overall": 0.91, "freshness": "verified 12d ago"},
    "rank": {"score": 0.88, "signals": {"intent_relevance": 0.94, "personal_fit": 0.8}},
    "followed": true
  }], "next_cursor": null }
```

## 7. Creator module (`creator`) — no-code creation **[PRD flow]**

| Method | Path | Description |
|---|---|---|
| POST | `/creator/interviews` | start interview: `{intent_statement: "I want to help people…"}` |
| POST | `/creator/interviews/{id}/answers` | answer next gap-question → next question or draft |
| POST | `/creator/interviews/{id}/generate` | → draft ServiceSpecification |
| GET | `/creator/interviews/{id}/spec` | review draft spec |
| PATCH | `/creator/interviews/{id}/spec` | creator corrections (truth review only) |
| POST | `/creator/interviews/{id}/simulate` | run simulation suite (async job) |
| GET | `/creator/simulations/{job_id}` | case-by-case results + scores |
| POST | `/creator/interviews/{id}/qualify` | request qualification run |
| GET | `/creator/qualifications/{id}` | result: READY_TO_PUBLISH / NEEDS_IMPROVEMENT / RESTRICTED |
| POST | `/creator/interviews/{id}/publish` | visibility + publish (after qualification) |
| GET | `/creator/services/{id}/insights` | AI-generated creator insights |
| GET | `/creator/services/{id}/metrics` | users, successful sessions, returned, useful, gaps |

Interview question sequence is conversation-style **[PRD: Conversation over Configuration]**:

```jsonc
// POST /creator/interviews/{id}/answers
{ "answers": [{"question_id": "q3", "text": "Beginner to intermediate photographers"}] }
// → { "next_question": {"id": "q4", "text": "What should the outcome look like?"},
//     "gaps_detected": ["boundaries", "success_definition"] }
```

## 8. Knowledge module (`knowledge`)

| Method | Path | Description |
|---|---|---|
| POST | `/knowledge/collections` | create collection |
| POST | `/knowledge/collections/{id}/sources` | add source (upload/URL) — triggers ingestion job |
| GET | `/knowledge/sources/{id}` | status incl. freshness fields |
| POST | `/knowledge/sources/{id}/verify` | re-verify freshness |
| POST | `/knowledge/collections/{id}/versions` | freeze a KnowledgeVersion |
| GET | `/knowledge/collections/{id}` | documents & chunk stats |

Creator UX never exposes "RAG" **[PRD]** — the API is internal-facing for the creator UI
("add my training material").

## 9. Runtime & Tools module (`runtime`)

| Method | Path | Description |
|---|---|---|
| GET | `/runtime/tools` | tool registry (admin) |
| POST | `/runtime/tools` | register tool (schemas, risk class, timeout) |
| GET | `/runtime/models` | model catalog & routing policy (admin) |
| PATCH | `/runtime/models/policy` | weights: capability/cost/latency/quality |

Internal (not public HTTP): `ModelGateway.invoke(needs, messages, tools)` and
`ToolExecutor.run(tool_id, input, policy)`.

## 10. Permission module (`permission`)

| Method | Path | Description |
|---|---|---|
| POST | `/permissions/requests` | service requests context (internal, surfaced in chat UX) |
| POST | `/permissions/grants` | user decides (same shape as §3 grant) |
| GET | `/permissions/audit` | user-visible log: what was shared, when, with whom |

The runtime **must** call `permission.resolve(user, service, context_types)` before context
reaches a service *(PRD hard rule: least-context privilege)*.

## 11. Outcome module (`outcome`)

| Method | Path | Description |
|---|---|---|
| GET | `/sessions/{id}` | session detail incl. outcome |
| POST | `/sessions/{id}/outcome/confirm` | user confirmation + structured feedback |
| GET | `/services/{id}/outcomes` | public aggregate (success rate, common outcomes) |

```jsonc
// POST /sessions/{id}/outcome/confirm
{ "useful": true, "achieved_goal": true, "notes": "Got a real itinerary",
  "signals": {"practice_completed": true, "feedback_generated": true} }
```

## 12. Qualification module (`qualification`)

| Method | Path | Description |
|---|---|---|
| GET | `/qualification/runs/{id}` | scores per criterion + duplicate report |
| POST | `/qualification/runs/{id}/re-run` | after improvements |

## 13. Reputation & Trust module (`reputation`)

| Method | Path | Description |
|---|---|---|
| GET | `/services/{id}/trust` | service trust components |
| GET | `/creators/{id}/reputation` | creator reputation components |
| GET | `/reputation/events` | admin/audit feed |

## 14. Analytics module (`analytics`)

| Method | Path | Description |
|---|---|---|
| GET | `/creator/analytics/overview` | cross-service dashboard |
| GET | `/creator/analytics/insights` | AI insights list |
| POST | `/creator/analytics/insights/{id}/dismiss` | dismiss insight |

## 15. Reward module (`reward`) — off-chain **[PRD]**

| Method | Path | Description |
|---|---|---|
| GET | `/rewards/me` | balance (available, frozen) + pending events |
| GET | `/rewards/ledger` | ledger entries (cursor, owner only) |
| GET | `/rewards/rules` | public earning rules |
| POST | `/rewards/payouts` | (post-MVP) request payout |

Rewards are triggered server-side from outcome events — never by client calls.

---

## 16. Core flow sequence (normative)

### 16.1 Consumer message loop

```
POST /conversations/{id}/messages
  → intent.analyze                     (intent)
  → personal_qora.resolve_context      (memory + goals)
  → service.match(candidates)          (intent graph + ranking)
  → permission.resolve(...)            (grants; may return permission_request)
  → runtime.execute(service_version)   (model gateway + tools + guardrails)
  → outcome.evaluate(session)
  → reputation.apply_events(...)
  → reward.process(session outcome)
  → response (message + trace_id + outcome)
```

### 16.2 Creator publish loop

```
POST /creator/interviews → answers → generate(spec) → simulate → qualify → publish
  → service.create + service_version(v1)
  → lifecycle: draft → testing → qualification_pending → ready → published
```

### 16.3 Failure recovery

```
runtime failure → FAILURE_EVENTS(failure_type)
  → recovery options in response: continue_with_qora | try_another_service | retry | stop
  → POST /conversations/{id}/recovery {option}
```
