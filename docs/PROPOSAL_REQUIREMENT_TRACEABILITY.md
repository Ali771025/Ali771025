# ماتریس ردیابی تخصصی پروپوزال فنی سامانه هوشمند گزارش‌ساز و NL2SQL

منبع بررسی: `پروپوزال_فنی_سامانه_هوشمند_گزارش_ساز_RFP.pdf`، نسخه ۱.۰، ۱۵ صفحه.

## جمع‌بندی اجرایی

پروپوزال، محصول را یک سکوی چندنرم‌افزاری و چندنسخه‌ای برای تبدیل درخواست فارسی به SQL پارامتری، ممیزی‌پذیر و کنترل‌شده می‌داند که سرویس مرکزی هیچ دسترسی مستقیم به دیتابیس عملیاتی شهرداری ندارد. اجرای SQL باید در محیط On-Premise و بعد از اعتبارسنجی مجدد Connector انجام شود. محورهای اصلی سند عبارت‌اند از:

- Identity/Tenant با Keycloak/OIDC، MFA و Service Account
- API Gateway با Kong، Rate Limit، API Key، mTLS و Quota
- Knowledge Registry نسخه‌ای، Snapshot، Approval و Rollback
- Document Standardizer، Grounding، Conflict و Quality Score
- Hybrid Retrieval، Schema Graph، Query Planner و SQL Validator/AST Guard
- Model Router، Circuit Breaker، Failover، Cost Policy
- Exact/Semantic Cache و Recipe بر اساس Access Fingerprint
- Billing Wallet، Tariff، Reservation/Settlement، Ledger و Payment Reconciliation
- Audit/Observability با Redaction، OpenTelemetry، APM، Prometheus/Grafana
- Admin Web RTL و پنل‌های مالک و مدیر نرم‌افزار

## وضعیت فعلی کد در برابر الزامات پروپوزال

| کد | الزام پروپوزال | وضعیت فعلی | فایل/ماژول مرتبط | کار باقی‌مانده Production |
|---|---|---|---|---|
| PR-01 | دریافت درخواست با `software_id`, `version`, `user`, `scope claims`, token | انجام‌شده پایه | `POST /api/v1/reports/generate`, `ReportRequestIn` | اتصال کامل به JWT/Keycloak و API Gateway |
| PR-02 | اعتبارسنجی JWT/API Key، Tenant، Quota | انجام‌شده تخصصی برای مسیر گزارش | `AccessControlService`, `APIKeyAuthService`, `TokenAccountingService` | انتقال enforcement به Gateway + middleware سراسری همه endpointها |
| PR-03 | Policy Engine برای موضوع، جدول، ستون، نقش، Scope | انجام‌شده بخشی | `access_control.py`, RBAC Matrix endpoint | Policy DSL سطح جدول/ستون و تست Cross-Tenant کامل |
| PR-04 | Recipe/RAG/Graph/Planner/Generator | اسکلت و rule-based | `nl2sql.py`, Knowledge/Schema models | تکمیل Orchestrator واقعی و جدا از API |
| PR-05 | SQL Guard با AST، Read-only، Allowlist، Limit، Complexity | انجام‌شده پایه | `validate_connector_sql`, policy fields | AST parser واقعی T-SQL/PostgreSQL، منع `SELECT *` و Complexity Budget |
| PR-06 | Response شامل SQL، Parameters، Display Spec، Confidence و Audit ID | انجام‌شده | `ReportSuccess`, `DisplaySpec` | کالیبراسیون Confidence و Display Spec واقعی بر اساس Query Plan |
| PR-07 | اجرای SQL فقط داخل On-Premise Connector | قرارداد رعایت شده | `connector.py`, `/reports/execution-result` | ساخت Agent/SDK نصب‌شونده، mTLS و local SQL parser |
| PR-08 | Telemetry بدون داده حساس | انجام‌شده پایه | `AuditLog`, Redaction, RequestContextMiddleware | OpenTelemetry، Elastic APM، Prometheus/Grafana |
| PR-09 | Knowledge Snapshot مستقل با Draft/Review/Approved/Retired | انجام‌شده پایه | `KnowledgeDocument`, `KnowledgeSnapshot`, use cases | State machine کامل، Approval Policy و reviewer workflow |
| PR-10 | Delta ingestion، Hash، جلوگیری از فایل تکراری/متناقض | انجام‌شده بخشی | `knowledge.py`, standardize use case | File upload pipeline، MIME/AV/encoding، conflict resolution workflow |
| PR-11 | Snapshot atomic publish و Rollback | انجام‌شده پایه | `PublishSnapshotUseCase`, rollback endpoint | enforcing 20 gold tests و schema suspicious relations before publish |
| PR-12 | پنل مالک: مدیران، نقش، دسترسی، مالی، پرداخت، آمار، Audit | اسکلت عملیاتی | `owner.py`, `advanced_operations.py`, 15 owner pages | اختصاصی‌سازی همه صفحات و queryهای واقعی server-side |
| PR-13 | پنل مدیر نرم‌افزار: نسخه، دانش، کاربر، API Key، کیفیت، Recipe | اسکلت عملیاتی | `software.py`, `pageRegistry.ts` | UI اختصاصی برای ۱۹ صفحه و workflowهای review/conflict/schema graph |
| PR-14 | API Key lifecycle: issue/rotate/revoke/scope/IP/expiry | انجام‌شده بخشی | `issue_api_key`, `APIKeyRotationUseCase`, `APIKeyAuthService` | overlap expiry enforcement، IP allowlist واقعی و rate usage |
| PR-15 | Quality: feedback, gold test, dataset promotion, regression | انجام‌شده پایه | `Feedback`, `GoldTest`, `GoldTestRegressionUseCase` | dataset promotion و semantic comparison واقعی |
| PR-16 | Cache: Exact/Semantic با version/access fingerprint | مدل و Recipe پایه | `Recipe`, `cache_fingerprint`, docs | cache store واقعی Redis/pgvector و invalidation کامل |
| PR-17 | Billing: Wallet, Tariff, Reservation/Settlement, Ledger, Payment Reconciliation | انجام‌شده بخشی | `TokenAccountingService`, `WalletLedger`, `Payment` | double-entry ledger، reservation/settlement، gateway callback idempotency |
| PR-18 | Model Router: Local/Cloud، health، circuit breaker، failover | مدل و endpoint تست پایه | `AIModel`, `ModelPolicy`, `/owner/models/{id}/test` | router runtime، health probes، cost policy و failover واقعی |
| PR-19 | محرمانگی: عدم خروج داده خام، Redaction، retention per tenant | انجام‌شده پایه | `redact`, Audit, docs | retention jobs، hash chain audit و legal hold |
| PR-20 | استک منتخب: Python 3.12/FastAPI/PostgreSQL/Redis/React/Docker | انجام‌شده نزدیک | `pyproject`, docker compose, frontend | Keycloak/Kong/Timescale/Elasticsearch/pgvector/worker production profile |
| PR-21 | ۲۰ هفته برنامه و milestoneها | مستند شده | `docs/PAGE_MAP_45.md`, README | تبدیل به Jira/Project backlog و acceptance gates |
| PR-22 | Deliverables: source, migrations, Docker, docs, tests, runbook, SBOM | انجام‌شده بخشی | repo docs/tests/docker | Runbook کامل، SBOM، security/load/E2E reports |
| PR-23 | Acceptance: ۲۰ سؤال ۱۰۰٪، benchmark ۹۰٪، zero unsafe SQL | آماده‌سازی شده | Gold tests, Regression use case | مجموعه ۲۰ Gold SQL واقعی کارفرما و semantic evaluator |
| PR-24 | SLA: P95 cache <1s، non-cache <12s، failover/circuit breaker | مدل‌سازی شده | dashboard/meta docs | load test و observability واقعی |

## اقدامات انجام‌شده بعد از خواندن PDF

1. PDF از commit آپلودی بازیابی و متن آن در `docs/PROPOSAL_EXTRACTED_TEXT.md` استخراج شد.
2. مسیر گزارش با API Key واقعی‌تر شد: `X-API-Key`، hash verification، وضعیت، انقضا و scope merge.
3. Token Accounting با quota روزانه/ماهانه کاربر و Tenant، سقف هزینه و سقف Token تکمیل شد.
4. Frontend برای صفحه درخواست گزارش از Blueprint عمومی به فرم واقعی RHF+Zod تبدیل شد.
5. تست‌های Backend و Frontend افزایش یافتند.

## اولویت اجرای باقی‌مانده

### P0 — قبل از Pilot قابل قبول

- Keycloak/Kong integration واقعی یا حداقل adapter production-ready.
- SQL AST validator واقعی با allowlist table/column و forbidden multi-statement.
- Connector local agent/SDK با mTLS، policy hash، TTL و snapshot hash.
- ۲۰ Gold Test واقعی کارفرما با Gold SQL/Dataset ثابت.
- Tenant filter سراسری در Repository همه endpointهای مدیریتی.

### P1 — قبل از Pre-Production

- Snapshot publish gate کامل: conflict, validator, 20 gold tests, approvers.
- Document upload pipeline با MIME/AV/checksum/encoding/preview.
- RBAC Matrix UI واقعی و policy conflict detection.
- Billing double-entry + payment callback/reconciliation.
- Observability stack و dashboards واقعی.

### P2 — تحویل نهایی

- SBOM، Runbook، Backup/Restore drill، load/security reports.
- UAT workflow و training docs.
- React Router/Monaco بعد از رفع advisory امنیتی نسخه‌های وابسته.
