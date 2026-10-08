# QORA — Technical Architecture & Development Blueprint v1.0

> Consolidated from the client's **PRD v1.0** and **Prototype v0.3**, following the owner-review
> architecture note. Every claim is tagged:
>
> · **[PRD]** — a hard requirement implied by the client document (Vision / Scope / User Story / MVP).
> · **[TECH]** — a proposed engineering decision that the PRD does not fix. Replaceable without
> violating the contract.
>
> This document is the single source of truth for the next pipeline steps:
> **ERD** → **API Contract** → **Development Phasing** → **Codex Prompts** → implementation.

---

## 1. Engineering definition of the product

QORA, from a backend point of view, is all of the following at once **[PRD]**:

```
Consumer AI Platform
      +  Personal AI
      +  AI Service Network
      +  No-Code AI Service Creator
      +  AI Orchestration Layer
      +  Outcome / Trust / Reputation Network
      +  Future Reward Economy
```

The governing UX principle **[PRD]**:

> The user must never touch Agent, Model, Prompt, RAG, Tool or Workflow directly.
> The UX stays a simple Consumer App. All complexity lives behind the platform.

### Conceptual architecture (the backbone) **[PRD]**

```
PERSON / PROFILE
       ↓
PERSONAL QORA            (Memory • Intent • Goals • Preferences)
       ↓
INTENT ROUTER / ORCHESTRATOR
       ↓
QORA SERVICE NETWORK
       ↓
SERVICE RUNTIME          (Knowledge • Behavior • Tools • Rules • Outcome)
       ↓
OUTCOME ENGINE
       ↓
TRUST + REPUTATION
       ↓
REWARD ENGINE
```

Every module, table and endpoint proposed below must map onto this chain.

---

## 2. Macro architecture **[TECH]**

**Modular Monolith + logically separated AI Runtime.** Not microservices on day one.

```
                │  Web / Mobile UI  │
                        │
                │   API / BFF Layer │
                        │
   ┌────────────────────┼─────────────────────┐
   ▼                    ▼                     ▼
Identity & Profile  Conversation Core   Creator Platform
   │                    │                     │
   └────────────────────┼─────────────────────┘
                        ▼
              │    PERSONAL QORA      │
              │ Context / Memory / Goals │
                        ▼
              │    AI ORCHESTRATOR    │
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  Intent Engine   Service Matcher  Policy Engine
                        ▼
              │    SERVICE RUNTIME   │
              │ Model Gateway        │
              │ RAG / Knowledge      │
              │ Tools / Connectors   │
              │ Service Rules        │
              │ Guardrails           │
                        ▼
              │    OUTCOME ENGINE    │
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Trust      Reputation     Analytics
                        │
                        ▼
                 Reward Ledger
```

### Why not full microservices now **[TECH]**

MVP only has to prove the loop **Consumer + Creator + Useful Outcome** **[PRD]**.
The PRD explicitly excludes from MVP: Large Marketplace, Complex Workflow Builder,
Full Enterprise Admin, Immediate On-chain Settlement.

Therefore, day-one infrastructure such as 30 microservices, a Kafka cluster, Kubernetes,
a graph database, a dedicated vector DB and a service mesh is over-engineering.

### Module map (boundaries must allow later extraction) **[TECH]**

```
qora-backend/
├── identity/        # User, auth, sessions, devices, account status
├── profile/         # Private profile, public creator profile, business profile
├── personal_qora/   # Memory, goals, preferences, context, journeys
├── conversation/    # Conversations, messages, traces, invocations
├── intent/          # Intent engine, intent graph, entities, capabilities
├── service/         # Registry, versions, lifecycle, discovery, follow
├── creator/         # Interview, spec generator, simulation, qualification
├── runtime/         # Orchestration, model gateway, tools, guardrails
├── knowledge/       # Sources, documents, chunks, collections, freshness
├── permission/      # Context grants, least-context resolver
├── outcome/         # Outcome definitions, evaluation, failure recovery
├── qualification/   # Qualification runs, duplicate detection
├── reputation/      # Trust scores, reputation events
├── analytics/       # Session events, creator metrics, AI insights
└── reward/          # Reward events, eligibility, off-chain ledger
```

---

## 3. Stack **[TECH]**

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React / Next.js | existing prototype is React + Vite — either is fine |
| Backend | Python + FastAPI | orchestration / retrieval / evaluation are Python-heavy |
| ORM | SQLAlchemy 2.0 | portable SQLite → PostgreSQL |
| Validation | Pydantic v2 | |
| Main DB | PostgreSQL | |
| Semantic vector | pgvector (MVP) | dedicated vector DB only if scale demands |
| Cache / queues | Redis | |
| Background jobs | Celery / Dramatiq / ARQ | interviews, simulation runs, ingestion |
| Files | S3-compatible object storage | knowledge uploads |
| AI Gateway | internal abstraction over OpenAI/Anthropic/Google/Local | no direct provider coupling |
| RAG | internal abstraction | never exposed to UI |
| Search (MVP) | PostgreSQL full-text + vector | OpenSearch/Elasticsearch later if needed |
| Auth | OAuth2/OIDC + secure sessions/tokens | |
| Observability | OpenTelemetry | |
| Errors | Sentry-compatible | |
| Containers | Docker | |
| Deploy (early) | Docker Compose / managed containers | Kubernetes only when real need appears |

---

## 4. Domain specifications

### 4.1 Identity Domain **[PRD]**

Owns: User, Authentication, Identity, Account Status, Sessions, Devices, Security.

**One user is never split into a separate Consumer user and Creator user** **[PRD]**:

```
User
 ├── Private Profile
 ├── Personal QORA Profile
 ├── optional Creator Profile
 └── optional Business Profile
```

A Person may be Consumer, Creator, or both (matches the PRD primitives *Person* and *Creator*).

### 4.2 Private vs Public profile separation **[PRD — critical]**

```
PRIVATE USER PROFILE              PUBLIC CREATOR PROFILE
────────────────────              ──────────────────────
Name                              Display name
Language                          Bio
Timezone                          Expertise
Preferences                       Verification
Goals                             Published services
Personal memories                 Creator reputation
Career data                       Public identity
Travel preferences …
```

**Private data must never leak from the user profile into the creator profile.**
The prototype already separates Public Identity from QORA's private understanding.

### 4.3 Personal QORA Domain **[PRD]**

```
PersonalQora
 ├── Preferences
 ├── Goals
 ├── Memories
 ├── Context
 ├── Intent History
 ├── Active Journeys
 ├── Followed Services
 ├── Saved Services
 ├── Previous Outcomes
 └── Context Permissions
```

Expectations **[PRD]**: know the user, understand intent, answer directly, invoke the right
service, coordinate multiple capabilities, continue previous journeys.

### 4.4 Memory model **[TECH — data-model level not fixed by PRD]**

Memory is not one flat `memories` table. Logical classes:

| Memory type | Example |
|---|---|
| Profile Fact | user's job |
| Preference | prefers short answers |
| Goal | prepare for an interview |
| Persistent Context | language level |
| Journey State | current step of a study plan |
| Interaction Insight | prefers calm travel plans |
| Temporary Context | trip next week |

Every memory carries metadata **[TECH]**: `source, confidence, created_at, updated_at,
expires_at, sensitivity, user_editable, share_policy`.

### 4.5 Conversation Domain **[PRD]**

A conversation is not message storage only:

```
Conversation
 ├── Messages
 ├── Active Intent
 ├── Active Service
 ├── Active Journey
 ├── Context Snapshot
 ├── Service Invocations
 ├── Tool Invocations
 ├── Outcome
 └── Recovery State
```

Every user request gets a full trace **[TECH]**:

```
Message → Intent → Candidate Services → Chosen Service → Context shared
        → Model call → Tool calls → Response → Outcome
```

The trace is required later for debugging, reputation, evaluation and reward.

### 4.6 Intent Engine **[PRD]**

Input (example): *"Next week I have an English interview for a Product Manager position."*

Structured output **[TECH]**:

```yaml
primary_intent:      Job_interview_preparation
secondary_intents:   [English_speaking_practice]
entities:
  Role: Product Manager
  Date: next week
required_capabilities: [Interview_coaching, English_practice]
confidence:          0.94
```

The engine must perform: **Intent Detection, Intent Decomposition, Entity Extraction,
Ambiguity Detection, Capability Mapping** — not plain classification.

### 4.7 Intent Graph **[PRD]**

The PRD is explicit: QORA needs an **Intent Graph** in addition to any social graph, and ranking
must rest on intent relevance, outcome quality, repeat use, satisfaction, trust, freshness,
personal fit and exploration.

```
User ──has_intent──► Intent ──► Capability ──► Service ──► Outcome
```

MVP does **not** need Neo4j **[TECH]**. PostgreSQL holds:
`service_intents, service_capabilities, intent_relations, user_intent_history, service_outcomes`.
Graph infrastructure can be added later.

### 4.8 Service Registry **[PRD]**

A Service is a first-class entity — never "just a prompt".

```
Service
├── id · creator_id · slug · name · summary · description
├── purpose · audience · category · risk_level
├── visibility · lifecycle_status
├── current_version_id · verification_status · published_at
└── timestamps
```

PRD defines for every service: Purpose, Audience, Knowledge, Method, Behavior, Tools,
Boundaries, Outcome, Trust, Version.

### 4.9 Service Version **[PRD implied]**

```
Service ── v1 / v2 / v3 …

ServiceVersion
├── purpose · method · behavior · system_instructions · boundaries
├── knowledge_config · tools_config · outcome_definition
├── examples · evaluation_config · created_at
```

Enables: Rollback, A/B testing, quality comparison, re-evaluation, audit.

### 4.10 Service lifecycle **[PRD defines visibility; internals TECH]**

```
DRAFT → READY_FOR_TEST → TESTING → PRIVATE
                                      ├────► UNLISTED
                                      └────► QUALIFICATION_PENDING
                                               ├─► READY ─────► PUBLISHED → UPDATED → REQUALIFICATION
                                               ├─► IMPROVE
                                               └─► RESTRICTED
```

The three PRD visibilities: **Private · Unlisted · Public**; Public requires Qualification.

### 4.11 Service Runtime **[PRD — critical path]**

```
Service Invocation
  → Load Service Version → Load Runtime Policy → Resolve Required Context
  → Permission Check → Load Knowledge → Resolve Tools → Choose Model
  → Build Runtime Context → LLM Invocation → Possible Tool Calls
  → Guardrail → Response → Outcome Evaluation
```

### 4.12 Model Gateway **[TECH — PRD requires multi-model product layer]**

No service may depend directly on OpenAI/Anthropic/….

```
Service Runtime → Model Gateway
                   ├─ OpenAI   ├─ Anthropic
                   ├─ Google   └─ Local
```

Services declare **capabilities**, not APIs **[PRD concept]**:

```yaml
needs:
  reasoning: medium
  structured_output: true
  tool_calling: true
  long_context: false
```

Router selects provider by: capability, cost, latency, availability, policy, quality.

### 4.13 Knowledge / RAG **[TECH — PRD requires knowledge in every service]**

The creator never sees the word "RAG". UX: *"I want the service to use my training material."*

```
Upload → Safety scan → Extraction → Normalization → Chunking
       → Metadata → Embedding → Index → Knowledge Collection
```

Model: `KnowledgeSource, KnowledgeDocument, KnowledgeChunk, KnowledgeCollection, KnowledgeVersion`.
Every **Service Version** binds to a specific **Knowledge Version**.

### 4.14 Source Freshness **[PRD — freshness is part of Trust & Ranking]**

Documents carry `source_date, ingested_at, last_verified_at, expires_at, freshness_policy`.
Stale services must not rank like current ones.

### 4.15 Tool System **[TECH]**

```
Tool
├── id · name · capability
├── input_schema · output_schema
├── auth_requirement · risk_class
├── allowed_services · timeout
```

The runtime — not the LLM — controls tool access. Flow:

```
LLM → Tool Request → Tool Policy → Permission → Validation
    → Execution → Result validation → LLM
```

### 4.16 Permission Engine **[PRD — explicit]**

> Personal Context is never given to a Service without permission.

```
ContextGrant
├── user_id · service_id · context_type · scope
├── mode (ALLOW_ONCE | ALWAYS_ALLOW | DENY)
├── granted_at · expires_at · revoked_at
```

The prototype shows exactly this UX.

### 4.17 Context Isolation **[PRD principle: least-context privilege]**

```
Personal QORA (knows: name, career, medical, family, travel, goals)
        ↓ Context Resolver
Minimal Required Context   (Interview Coach: career history, target role, goals)
        ↓ Permission
Service
```

### 4.18 Creator Platform **[PRD — fixed flow]**

```
Intent → Interview → Generate → Simulate → Review → Visibility → Qualify
```

The creator backend is itself an internal AI agent/workflow.

### 4.19 Creator Interview Engine **[PRD: Conversation over Configuration]**

First question: *"What should people be able to do?"*
Then the system finds specification gaps and asks targeted questions
(audience level, budget, method, negative boundaries, success definition) —
never a 40-field form.

### 4.20 Service Specification Generator **[PRD]**

After the interview QORA drafts: Purpose, Audience, Intent, Capabilities, Method, Behavior,
Knowledge requirements, Boundaries, Outcome definition, Examples, Risk classification.
The creator only reviews truth and important corrections.

### 4.21 Simulation Engine **[TECH — PRD requires pre-publish testing]**

Scenarios: normal, ambiguous, edge-case, boundary, unsafe, unsupported, adversarial.
Per scenario record: `TestCase, ExpectedBehavior, ActualBehavior, Evaluation, Score, FailureReason`.

### 4.22 Qualification Engine **[PRD criteria]**

Criteria: Utility, Quality, Differentiation, Safety, Completeness, Reliability (+ duplicate control).

```
QualificationRun
 ├── Specification Check · Outcome Check · Safety Evaluation
 ├── Boundary Evaluation · Reliability Simulation
 ├── Duplicate Detection · Knowledge Check · Trust Requirement Check
 └── Result: READY_TO_PUBLISH | NEEDS_IMPROVEMENT | RESTRICTED
```

### 4.23 Duplicate Detection **[TECH — required by PRD's differentiation criterion]**

Not name comparison. Embed `intent, capability, outcome` per service; flag similar candidates.
Response is a **question**, not a rejection: *"This is very similar to 4 existing services —
what makes your method different?"*

### 4.24 Discovery Engine **[PRD]**

Explore is not a popularity marketplace.

```
Query → Intent → Candidate Retrieval → Eligibility → Ranking → Diversification → Results

Score = Intent Relevance + Outcome Quality + Personal Fit + Trust
      + Satisfaction + Repeat Use + Freshness + Exploration
```

The signal families are fixed by the PRD; exact weights are **not** — they must be
configurable **[TECH]**.

### 4.25 Follow ≠ Social Follow **[PRD]**

Follow means *"add this intelligence to my personal toolkit"*. Following an Interview Coach
raises personal fit for future interview intents — not just notifications.

### 4.26 Outcome Engine **[PRD — North Star: Successful Service Sessions]**

Every service has an **Outcome Definition** (e.g. Travel Planner: *"a usable itinerary covering
dates, budget and priorities"*).

```
Session: Started → Relevant interaction → Deliverable generated
       → Outcome evaluator → SUCCESS | PARTIAL | FAILED | UNKNOWN
```

### 4.27 Outcome validation is not just "Like" **[TECH]**

```
Outcome Score = Service signals + Completion signals + Structured evaluation
              + User confirmation + Follow-up behavior
```

Example (Interview Coach): `practice_completed ✓ · feedback_generated ✓ ·
role_specific ✓ · user_useful ✓`

### 4.28 Failure Recovery **[PRD prototype state → TECH taxonomy]**

The prototype's recovery UX ("Service could not complete → continue with QORA **or** try another
service") is a PRD requirement. The taxonomy is technical:

```
MODEL_FAILURE · TOOL_FAILURE · MISSING_CONTEXT · PERMISSION_DENIED
KNOWLEDGE_FAILURE · SERVICE_UNAVAILABLE · POLICY_BLOCK · TIMEOUT · LOW_CONFIDENCE
```

Orchestrator reaction: retry · fallback model · fallback service · direct QORA answer ·
ask user · stop safely.

### 4.29 Trust Engine **[PRD]**

Keep **Creator Trust** and **Service Trust** separate — a trusted creator's brand-new service
does not inherit a high service score.

### 4.30 Risk Classification **[PRD: verification is risk-based]**

```
LOW (writing editor, travel planner) → MEDIUM (career coach)
→ HIGH (finance, medical) → RESTRICTED
```

### 4.31 Reputation Engine **[TECH shape, PRD signals]**

Event-driven, never a single stored number — keep component scores:

`successful_outcome · confirmed_complaint · repeat_use · quality_update ·
verification · safety_failure · stale_knowledge`

### 4.32 Creator Analytics **[PRD prototype surface]**

Users this week · Successful sessions · Returned · Useful · Knowledge gap ·
Suggested improvement · Estimated reward.

Pipeline **[TECH]**: `ServiceSession → Events → Aggregation → CreatorMetrics → Insight Generator`

### 4.33 AI-generated Creator Insights **[PRD feature, TECH implementation]**

*"17 users asked for a shorter checklist."*

```
Session signals → cluster unmet requests → detect recurring gap
→ generate creator insight → suggest service update
```

Start simple in MVP; grow later.

### 4.34 Reward Engine **[PRD — MVP is off-chain]**

For MVP: **Reward ≠ Blockchain transfer.**

```
Reward Event → Eligibility → Anti-Abuse → Reward Calculation → Off-chain Ledger
```

Rewards attach to **useful outcomes and real users** **[PRD]** — messages, views, likes and
followers are explicitly **not** reward bases.

### 4.35 Reward Ledger *(completed — the source document was cut off here)* **[TECH]**

Double-entry, append-only, off-chain; a future chain settlement is an adapter, not the ledger.

```
RewardAccount        per user (creator or consumer)
RewardLedgerEntry    immutable double-entry rows (debit/credit pair per event)
RewardEvent          the trigger (successful outcome, bonus, correction…)
RewardRule           configurable earning rules + anti-abuse thresholds
RewardPayoutRequest  (future) withdrawal / settlement batch
```

Suggested fields:

```
RewardAccount   { id, user_id, balance_units, frozen_units, status, created_at }
RewardLedgerEntry { id, account_id, event_id, direction(CREDIT|DEBIT), units,
                    reason, idempotency_key, created_at }
RewardEvent     { id, subject_type, subject_id, kind, units, quality_multiplier,
                  status(PENDING|ELIGIBLE|SETTLED|REVERSED), occurred_at, settled_at }
RewardRule      { id, name, kind, base_units, multiplier_field, cap, window, active }
```

Rules **[PRD-aligned]**:
1. Only `outcome.status in (SUCCESS, PARTIAL)` with real-user confirmation generates rewards.
2. Every entry carries an `idempotency_key` (event + subject) — replays never double-pay.
3. Suspected abuse freezes `frozen_units` and marks the event `REVERSED` after review.
4. Corrections are compensating entries, never updates of past rows.
5. Chain settlement (future) reads `SETTLED` batches; the ledger stays authoritative.

---

## 5. North Star & measurement **[PRD]**

- **North Star:** Successful Service Sessions.
- Ranking inputs: intent relevance, outcome quality, repeat use, satisfaction, trust,
  freshness, personal fit, exploration (weights configurable).
- Reward correlates with useful outcomes, never engagement vanity metrics.
- MVP exit: the Consumer + Creator + Useful Outcome loop is proven end-to-end.

## 6. Non-goals for MVP **[PRD]**

Large marketplace · complex workflow builder · full enterprise admin ·
immediate on-chain settlement · graph infrastructure · dedicated vector DB ·
Kubernetes/service mesh (all deferred until real need).

---

*Next artifacts in the pipeline (see sibling files):* `ERD.md` · `API_CONTRACT.md` ·
`PHASING.md` · `CODEX_PROMPTS.md`
