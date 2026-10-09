# QORA — ERD v1.0 (Entity Relationship Diagram)

> Derived from `ARCHITECTURE.md`. PostgreSQL target; types are logical (UUID PKs, timestamptz).
> Diagrams are split per domain cluster for readability. All FKs cross clusters are listed after
> each diagram. `P*` = PRD-implied, `T*` = technical proposal.

---

## 0. ERD index

| Cluster | Entities | Diagram |
|---|---|---|
| A · Identity & Profiles | users, sessions, devices, private_profiles, creator_profiles, business_profiles | §1 |
| B · Personal QORA | personal_profiles, memories, goals, preferences, journeys, saved/followed, context_grants | §2 |
| C · Conversation & Traces | conversations, messages, invocation_traces, service_invocations, tool_invocations | §3 |
| D · Intent Graph | intents, intent_entities, capabilities, intent↔capability↔service links, user_intent_history | §4 |
| E · Service Registry | services, service_versions, lifecycle_transitions, knowledge_* , tools | §5 |
| F · Runtime, Sessions & Outcome | service_sessions, session_events, model_calls, outcome_records, failure_events | §6 |
| G · Qualification & Simulation | qualification_runs, simulation_cases, simulation_results, duplicate_checks | §7 |
| H · Trust, Reputation & Analytics | trust_scores, reputation_events, creator_metrics, insight_reports | §8 |
| I · Reward Economy | reward_accounts, reward_events, reward_ledger_entries, reward_rules | §9 |

---

## 1. Cluster A — Identity & Profiles

```mermaid
erDiagram
    USERS ||--o{ SESSIONS : has
    USERS ||--o{ DEVICES : has
    USERS ||--|| PRIVATE_PROFILES : "1:1 mandatory"
    USERS ||--o| CREATOR_PROFILES : "0..1 optional"
    USERS ||--o| BUSINESS_PROFILES : "0..1 optional"

    USERS {
        uuid id PK
        string email UK
        string phone "nullable UK"
        string password_hash
        string auth_provider "local|google|..."
        string account_status "active|suspended|deleted"
        timestamptz created_at
        timestamptz updated_at
    }
    SESSIONS {
        uuid id PK
        uuid user_id FK
        string refresh_token_hash
        string device_id FK
        inet ip
        string user_agent
        timestamptz expires_at
        timestamptz revoked_at
    }
    DEVICES {
        uuid id PK
        uuid user_id FK
        string platform "web|ios|android"
        string fcm_token "nullable"
        timestamptz last_seen_at
    }
    PRIVATE_PROFILES {
        uuid id PK
        uuid user_id FK "UK"
        string display_name
        string language
        string timezone
        date birth_date "sensitive"
        jsonb preferences_snapshot
        timestamptz updated_at
    }
    CREATOR_PROFILES {
        uuid id PK
        uuid user_id FK "UK"
        string display_name
        text bio
        string headline
        jsonb expertise_tags
        string verification_status "none|pending|verified|restricted"
        float trust_score "denormalized cache"
        timestamptz published_at
    }
    BUSINESS_PROFILES {
        uuid id PK
        uuid user_id FK "UK"
        string org_name
        string tax_id "encrypted"
        jsonb billing
    }
```

**Key rules**
- `PRIVATE_PROFILES` must never be readable through public creator endpoints *(PRD: no leak)*.
- One `USERS` row may hold both private and creator profiles — never split accounts *(PRD)*.

---

## 2. Cluster B — Personal QORA

```mermaid
erDiagram
    USERS ||--|| PERSONAL_PROFILES : has
    PERSONAL_PROFILES ||--o{ MEMORIES : contains
    PERSONAL_PROFILES ||--o{ GOALS : contains
    PERSONAL_PROFILES ||--o{ JOURNEYS : tracks
    USERS ||--o{ CONTEXT_GRANTS : issues
    USERS ||--o{ FOLLOWED_SERVICES : follows
    USERS ||--o{ SAVED_SERVICES : saves

    PERSONAL_PROFILES {
        uuid id PK
        uuid user_id FK "UK"
        jsonb preferences
        jsonb context_snapshot
        timestamptz updated_at
    }
    MEMORIES {
        uuid id PK
        uuid personal_profile_id FK
        string kind "profile_fact|preference|goal|persistent_context|journey_state|interaction_insight|temporary_context"
        string subject
        text content
        string source "user|system|inferred"
        float confidence
        string sensitivity "public|private|sensitive"
        string share_policy "deny|ask|allow"
        bool user_editable
        timestamptz expires_at "nullable"
        timestamptz created_at
        timestamptz updated_at
    }
    GOALS {
        uuid id PK
        uuid personal_profile_id FK
        string title
        text description
        string status "active|paused|done|dropped"
        jsonb success_criteria
        timestamptz target_at
    }
    JOURNEYS {
        uuid id PK
        uuid personal_profile_id FK
        uuid goal_id FK "nullable"
        string kind "e.g. interview_prep|trip_planning"
        jsonb state "current step"
        jsonb history
        timestamptz updated_at
    }
    CONTEXT_GRANTS {
        uuid id PK
        uuid user_id FK
        uuid service_id FK "→ E"
        string context_type "career|medical|travel|preferences|..."
        string scope "fields allowed"
        string mode "ALLOW_ONCE|ALWAYS_ALLOW|DENY"
        timestamptz granted_at
        timestamptz expires_at "nullable"
        timestamptz revoked_at "nullable"
    }
    FOLLOWED_SERVICES {
        uuid user_id FK "PK part"
        uuid service_id FK "PK part → E"
        timestamptz followed_at
    }
    SAVED_SERVICES {
        uuid user_id FK "PK part"
        uuid service_id FK "PK part → E"
        timestamptz saved_at
    }
```

**Key rules**
- `MEMORIES.share_policy` + `CONTEXT_GRANTS` together enforce *least-context privilege* *(PRD)*.
- `FOLLOWED_SERVICES` feeds **personal fit** in discovery ranking *(PRD: follow = add to toolkit)*.

---

## 3. Cluster C — Conversation & Traces

```mermaid
erDiagram
    USERS ||--o{ CONVERSATIONS : starts
    CONVERSATIONS ||--o{ MESSAGES : contains
    CONVERSATIONS ||--o{ INVOCATION_TRACES : records
    INVOCATION_TRACES ||--o{ MODEL_CALLS : includes
    INVOCATION_TRACES ||--o{ TOOL_INVOCATIONS : includes
    CONVERSATIONS }o--|| INTENTS : "active_intent → D"
    CONVERSATIONS }o--|| SERVICES : "active_service → E"

    CONVERSATIONS {
        uuid id PK
        uuid user_id FK
        uuid active_intent_id FK "nullable → D"
        uuid active_service_id FK "nullable → E"
        uuid active_journey_id FK "nullable → B"
        jsonb context_snapshot
        string recovery_state "normal|service_failed|awaiting_permission"
        timestamptz created_at
        timestamptz updated_at
    }
    MESSAGES {
        uuid id PK
        uuid conversation_id FK
        string role "user|assistant|service|system"
        text content
        jsonb content_blocks "rich cards, suggestions"
        string status "sent|delivered|failed"
        timestamptz created_at
    }
    INVOCATION_TRACES {
        uuid id PK
        uuid conversation_id FK
        uuid message_id FK "triggering message"
        uuid intent_id FK "→ D"
        jsonb candidate_services "ids + scores"
        uuid chosen_service_id FK "nullable → E"
        uuid chosen_service_version_id FK "→ E"
        jsonb context_shared "what was granted"
        string outcome_status "SUCCESS|PARTIAL|FAILED|UNKNOWN"
        timestamptz started_at
        timestamptz finished_at
    }
    MODEL_CALLS {
        uuid id PK
        uuid trace_id FK
        string provider "openai|anthropic|google|local"
        string model
        int prompt_tokens
        int completion_tokens
        int latency_ms
        float cost_usd
        string status "ok|error"
    }
    TOOL_INVOCATIONS {
        uuid id PK
        uuid trace_id FK
        uuid tool_id FK "→ E"
        jsonb input
        jsonb output
        string status "ok|denied|error|timeout"
        int latency_ms
    }
```

---

## 4. Cluster D — Intent Graph

```mermaid
erDiagram
    INTENTS ||--o{ INTENT_ENTITIES : has
    INTENTS ||--o{ INTENT_CAPABILITY_MAP : requires
    CAPABILITIES ||--o{ INTENT_CAPABILITY_MAP : "required by"
    SERVICES ||--o{ SERVICE_INTENT_MAP : "serves → E"
    INTENTS ||--o{ SERVICE_INTENT_MAP : "served by"
    SERVICES ||--o{ SERVICE_CAPABILITY_MAP : "provides → E"
    CAPABILITIES ||--o{ SERVICE_CAPABILITY_MAP : "provided by"
    INTENTS ||--o{ INTENT_RELATIONS : "from"
    INTENTS ||--o{ INTENT_RELATIONS : "to"
    USERS ||--o{ USER_INTENT_HISTORY : has

    INTENTS {
        uuid id PK
        string slug UK "e.g. job_interview_preparation"
        string name
        text description
        uuid parent_intent_id FK "nullable, decomposition"
        string kind "primary|secondary|composite"
    }
    INTENT_ENTITIES {
        uuid id PK
        uuid intent_id FK
        string entity_type "Role|Date|Budget|Language|..."
        string value
    }
    CAPABILITIES {
        uuid id PK
        string slug UK "e.g. interview_coaching"
        string name
        text description
    }
    INTENT_CAPABILITY_MAP {
        uuid intent_id FK "PK part"
        uuid capability_id FK "PK part"
        float weight
    }
    SERVICE_INTENT_MAP {
        uuid service_id FK "PK part → E"
        uuid intent_id FK "PK part"
        float relevance "0..1, embedding+human"
    }
    SERVICE_CAPABILITY_MAP {
        uuid service_id FK "PK part → E"
        uuid capability_id FK "PK part"
        string level "basic|strong|native"
    }
    INTENT_RELATIONS {
        uuid from_intent_id FK "PK part"
        uuid to_intent_id FK "PK part"
        string relation "parent|similar|sequence|conflicts"
    }
    USER_INTENT_HISTORY {
        uuid id PK
        uuid user_id FK
        uuid intent_id FK
        uuid conversation_id FK "→ C"
        float confidence
        jsonb entities
        timestamptz occurred_at
    }
```

**Note (TECH):** this relational graph replaces Neo4j for MVP; `SERVICE_INTENT_MAP.relevance`
can later be recomputed from embeddings (`services.intent_embedding` in §5).

---

## 5. Cluster E — Service Registry, Knowledge & Tools

```mermaid
erDiagram
    USERS ||--o{ SERVICES : creates
    SERVICES ||--o{ SERVICE_VERSIONS : versions
    SERVICES ||--|| SERVICE_VERSIONS : "current_version_id"
    SERVICE_VERSIONS ||--o{ LIFECYCLE_TRANSITIONS : "history"
    SERVICE_VERSIONS }o--|| KNOWLEDGE_VERSIONS : "binds → knowledge"
    KNOWLEDGE_COLLECTIONS ||--o{ KNOWLEDGE_VERSIONS : has
    KNOWLEDGE_COLLECTIONS ||--o{ KNOWLEDGE_SOURCES : contains
    KNOWLEDGE_SOURCES ||--o{ KNOWLEDGE_DOCUMENTS : yields
    KNOWLEDGE_DOCUMENTS ||--o{ KNOWLEDGE_CHUNKS : split
    SERVICE_VERSIONS ||--o{ SERVICE_TOOL_MAP : "may use"
    TOOLS ||--o{ SERVICE_TOOL_MAP : "allowed in"

    SERVICES {
        uuid id PK
        uuid creator_id FK "→ creator_profiles"
        string slug UK
        string name
        text summary
        text description
        text purpose
        string audience
        string category
        string risk_level "LOW|MEDIUM|HIGH|RESTRICTED"
        string visibility "private|unlisted|public"
        string lifecycle_status "draft|ready_for_test|testing|private|unlisted|qualification_pending|ready|improve|restricted|published|updated|requalification"
        uuid current_version_id FK
        string verification_status "none|pending|verified|restricted"
        vector intent_embedding "pgvector, duplicate detection + discovery"
        timestamptz published_at
        timestamptz created_at
        timestamptz updated_at
    }
    SERVICE_VERSIONS {
        uuid id PK
        uuid service_id FK
        int version_no
        text purpose
        text method
        text behavior
        text system_instructions
        text boundaries
        jsonb knowledge_config
        jsonb tools_config
        jsonb outcome_definition "PRD: outcome per service"
        jsonb examples
        jsonb evaluation_config
        jsonb model_requirements "reasoning, tool_calling, ..."
        timestamptz created_at
    }
    LIFECYCLE_TRANSITIONS {
        uuid id PK
        uuid service_version_id FK
        string from_status
        string to_status
        uuid actor_id FK "→ users"
        text reason
        timestamptz created_at
    }
    KNOWLEDGE_COLLECTIONS {
        uuid id PK
        uuid creator_id FK
        string name
        text description
    }
    KNOWLEDGE_VERSIONS {
        uuid id PK
        uuid collection_id FK
        int version_no
        timestamptz created_at
    }
    KNOWLEDGE_SOURCES {
        uuid id PK
        uuid collection_id FK
        string kind "upload|url|api"
        string name
        timestamptz source_date
        timestamptz ingested_at
        timestamptz last_verified_at
        timestamptz expires_at
        string freshness_policy "stale_after_days|manual"
    }
    KNOWLEDGE_DOCUMENTS {
        uuid id PK
        uuid source_id FK
        string title
        text extracted_text
        string mime
        int size_bytes
        string scan_status "pending|clean|blocked"
    }
    KNOWLEDGE_CHUNKS {
        uuid id PK
        uuid document_id FK
        int seq
        text content
        vector embedding
        jsonb metadata
    }
    TOOLS {
        uuid id PK
        string name UK
        string capability
        jsonb input_schema
        jsonb output_schema
        string auth_requirement "none|user|service"
        string risk_class "LOW|MEDIUM|HIGH"
        int timeout_ms
    }
    SERVICE_TOOL_MAP {
        uuid service_version_id FK "PK part"
        uuid tool_id FK "PK part"
        jsonb policy "rate limits, params"
    }
```

---

## 6. Cluster F — Runtime Sessions & Outcome

```mermaid
erDiagram
    INVOCATION_TRACES ||--o| SERVICE_SESSIONS : "spawns → C"
    SERVICE_SESSIONS ||--o{ SESSION_EVENTS : emits
    SERVICE_SESSIONS ||--o| OUTCOME_RECORDS : evaluates
    SERVICE_SESSIONS ||--o{ FAILURE_EVENTS : may have
    OUTCOME_RECORDS }o--|| REPUTATION_EVENTS : "feeds → H"

    SERVICE_SESSIONS {
        uuid id PK
        uuid trace_id FK "→ C"
        uuid user_id FK
        uuid service_id FK "→ E"
        uuid service_version_id FK "→ E"
        string status "started|running|awaiting_permission|completed|failed|abandoned"
        jsonb context_shared
        timestamptz started_at
        timestamptz finished_at
    }
    SESSION_EVENTS {
        uuid id PK
        uuid session_id FK
        string kind "message|tool_call|model_call|permission_check|guardrail|recovery|..."
        jsonb payload
        timestamptz occurred_at
    }
    OUTCOME_RECORDS {
        uuid id PK
        uuid session_id FK "UK"
        uuid service_id FK "→ E"
        string status "SUCCESS|PARTIAL|FAILED|UNKNOWN"
        float score "0..1 composite"
        jsonb signals "service|completion|structured|confirmation|followup"
        bool user_confirmed
        text evaluator_notes
        timestamptz evaluated_at
    }
    FAILURE_EVENTS {
        uuid id PK
        uuid session_id FK
        string failure_type "MODEL_FAILURE|TOOL_FAILURE|MISSING_CONTEXT|PERMISSION_DENIED|KNOWLEDGE_FAILURE|SERVICE_UNAVAILABLE|POLICY_BLOCK|TIMEOUT|LOW_CONFIDENCE"
        string recovery_action "retry|fallback_model|fallback_service|direct_qora|ask_user|stop"
        text detail
        timestamptz occurred_at
    }
```

---

## 7. Cluster G — Qualification & Simulation

```mermaid
erDiagram
    SERVICES ||--o{ QUALIFICATION_RUNS : undergoes
    QUALIFICATION_RUNS ||--o{ SIMULATION_RESULTS : includes
    SIMULATION_CASES ||--o{ SIMULATION_RESULTS : "executed as"
    QUALIFICATION_RUNS ||--o{ DUPLICATE_CHECKS : includes

    QUALIFICATION_RUNS {
        uuid id PK
        uuid service_id FK "→ E"
        uuid service_version_id FK "→ E"
        string result "READY_TO_PUBLISH|NEEDS_IMPROVEMENT|RESTRICTED"
        jsonb scores "utility, quality, differentiation, safety, completeness, reliability"
        jsonb checks
        timestamptz started_at
        timestamptz finished_at
    }
    SIMULATION_CASES {
        uuid id PK
        string kind "normal|ambiguous|edge|boundary|unsafe|unsupported|adversarial"
        text input
        text expected_behavior
    }
    SIMULATION_RESULTS {
        uuid id PK
        uuid qualification_run_id FK
        uuid case_id FK
        text actual_behavior
        float score
        string failure_reason "nullable"
    }
    DUPLICATE_CHECKS {
        uuid id PK
        uuid qualification_run_id FK
        uuid similar_service_id FK "→ E"
        float similarity
        string resolution "unique|needs_differentiation|merge_suggested"
    }
```

---

## 8. Cluster H — Trust, Reputation & Analytics

```mermaid
erDiagram
    CREATOR_PROFILES ||--|| TRUST_SCORES : "creator_trust"
    SERVICES ||--|| TRUST_SCORES : "service_trust"
    OUTCOME_RECORDS ||--o{ REPUTATION_EVENTS : generates
    SERVICE_SESSIONS ||--o{ REPUTATION_EVENTS : generates
    SERVICES ||--o{ CREATOR_METRICS : aggregated
    CREATOR_METRICS ||--o{ INSIGHT_REPORTS : feeds

    TRUST_SCORES {
        uuid id PK
        string subject_type "creator|service"
        uuid subject_id
        float overall
        jsonb components "safety, reliability, quality, freshness"
        string verification_status
        timestamptz updated_at
    }
    REPUTATION_EVENTS {
        uuid id PK
        string subject_type "creator|service"
        uuid subject_id
        string kind "successful_outcome|confirmed_complaint|repeat_use|quality_update|verification|safety_failure|stale_knowledge"
        float delta
        jsonb meta
        timestamptz occurred_at
    }
    CREATOR_METRICS {
        uuid id PK
        uuid service_id FK "→ E"
        date bucket_date
        int users_count
        int successful_sessions
        int returned_users
        int useful_votes
        int unmet_request_count
    }
    INSIGHT_REPORTS {
        uuid id PK
        uuid service_id FK "→ E"
        string kind "knowledge_gap|improvement|demand_cluster"
        text summary "e.g. '17 users asked for a shorter checklist'"
        jsonb evidence
        string status "new|acted_on|dismissed"
        timestamptz created_at
    }
```

---

## 9. Cluster I — Reward Economy (off-chain ledger)

```mermaid
erDiagram
    USERS ||--|| REWARD_ACCOUNTS : has
    REWARD_ACCOUNTS ||--o{ REWARD_LEDGER_ENTRIES : accumulates
    REWARD_EVENTS ||--o{ REWARD_LEDGER_ENTRIES : "produces pair"
    REWARD_RULES ||--o{ REWARD_EVENTS : governs
    OUTCOME_RECORDS ||--o{ REWARD_EVENTS : "triggers (via status)"

    REWARD_ACCOUNTS {
        uuid id PK
        uuid user_id FK "UK"
        bigint balance_units
        bigint frozen_units
        string status "active|frozen|closed"
        timestamptz created_at
    }
    REWARD_EVENTS {
        uuid id PK
        string subject_type "session|outcome|creator|campaign"
        uuid subject_id
        string kind "outcome_reward|quality_bonus|correction|anti_abuse_reversal"
        bigint units
        float quality_multiplier
        string status "PENDING|ELIGIBLE|SETTLED|REVERSED"
        string idempotency_key UK
        timestamptz occurred_at
        timestamptz settled_at
    }
    REWARD_LEDGER_ENTRIES {
        uuid id PK
        uuid account_id FK
        uuid event_id FK
        string direction "CREDIT|DEBIT"
        bigint units
        string reason
        string idempotency_key UK
        timestamptz created_at
    }
    REWARD_RULES {
        uuid id PK
        string name UK
        string kind
        bigint base_units
        string multiplier_field
        bigint cap_units
        string window
        bool active
    }
```

**Ledger invariants (TECH):**
1. Entries are append-only — corrections are compensating rows.
2. Every reward produces a CREDIT row (and a DEBIT to the system mint account) — double entry.
3. `idempotency_key` on events **and** entries guarantees replay safety.
4. `balance_units = Σ credits − Σ debits`; `frozen_units` reserved during anti-abuse review.
5. Future on-chain settlement reads `SETTLED` batches only; the ledger stays authoritative.

---

## 10. Cross-cluster FK summary

| From | To | Meaning |
|---|---|---|
| context_grants.service_id | services.id | permission per service |
| conversations.active_intent_id | intents.id | active intent |
| invocation_traces.chosen_service_version_id | service_versions.id | exact version executed |
| tool_invocations.tool_id | tools.id | tool used |
| service_versions.knowledge_config → knowledge_version_id | knowledge_versions.id | bound knowledge |
| services.creator_id | creator_profiles.id | public creator identity |
| service_sessions.trace_id | invocation_traces.id | one session per trace |
| outcome_records.session_id | service_sessions.id | 1:1 evaluation |
| reward_events.subject_id | outcome_records.id / service_sessions.id | reward trigger |
| trust_scores.subject_id | creator_profiles.id / services.id | dual trust |
