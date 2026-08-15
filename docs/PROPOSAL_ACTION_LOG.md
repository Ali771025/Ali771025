# گزارش اقدام بر اساس نیازمندی‌های پروپوزال و RFP سامانه گزارش‌ساز هوشمند و NL2SQL

> فایل PDF پروپوزال از commit آپلودی repo بازیابی و خوانده شد. متن استخراج‌شده در `docs/PROPOSAL_EXTRACTED_TEXT.md` و ماتریس ردیابی تخصصی در `docs/PROPOSAL_REQUIREMENT_TRACEABILITY.md` ثبت شده است.

## محورهای تکمیل‌شده در این مرحله

### ۱. کنترل سطح دسترسی Backend

- `AccessControlService` اضافه شد.
- بررسی Tenant، وضعیت Tenant، مالکیت نرم‌افزار، وضعیت نرم‌افزار، وضعیت کاربر، Scope، Role و منطقه کاربر انجام می‌شود.
- برای هر درخواست گزارش، `policy_hash` و `access_fingerprint` تولید می‌شود.
- رد کنترل‌شده با reason codeهای تخصصی مانند `TENANT_INACTIVE`, `SOFTWARE_TENANT_MISMATCH`, `SCOPE_DENIED`, `REGION_SCOPE_DENIED` اضافه شد.

### ۲. محاسبه Token و کیف اعتبار گزارش

- `TokenAccountingService` اضافه شد.
- قبل از تولید گزارش، Prompt/Completion Token تخمین زده می‌شود.
- تعرفه فعال انتخاب و هزینه محاسبه می‌شود.
- مانده کیف اعتبار بررسی می‌شود.
- در صورت کافی‌بودن اعتبار، تراکنش مصرف در `WalletLedger` ثبت می‌شود.
- Idempotency برای جلوگیری از کسر اعتبار تکراری اضافه شد.
- API تخمین مستقل اضافه شد: `POST /api/v1/reports/token-estimate`.

### ۳. اعتبارسنجی API Key برای مسیر گزارش

- `APIKeyAuthService` اضافه شد.
- Header `X-API-Key` برای مسیر گزارش پشتیبانی می‌شود.
- کلید فعال/rotating و تاریخ انقضا بررسی می‌شود.
- Scopeهای API Key با Access Context درخواست ادغام می‌شود.
- `api_key_id` و `api_key_prefix` در درخواست و Audit ثبت می‌شود.

### ۴. Use Caseهای عملیاتی تکمیلی

- Tenant suspend/update policies/usage summary
- RBAC matrix/effective permissions
- Audit timeline
- Wallet operation با Idempotency-Key
- API Key rotation با دوره هم‌پوشانی
- Connector policy sync
- Gold test regression run

### ۵. Frontend حرفه‌ای‌تر

- `PermissionGuard` و `useSessionStore` اضافه شد.
- Hookهای Feature اضافه شدند:
  - `useTenantManagement`
  - `useKnowledgeWorkflow`
  - `useSnapshotPublish`
  - `useRequestMonitoring`
  - `useConnectorHealth`
- `TokenAccountingPanel` برای نمایش تخمین Token و هزینه در صفحات گزارش اضافه شد.
- API Clientهای Frontend برای مسیرهای جدید RBAC، Audit Timeline، Wallet، API Key Rotation، Regression، Policy Sync و Token Estimate کامل شدند.

## کارهای انجام‌شده پس از خواندن PDF واقعی

1. متن PDF استخراج و در `docs/PROPOSAL_EXTRACTED_TEXT.md` ذخیره شد.
2. ماتریس ردیابی تخصصی با الزام‌های کلیدی در `docs/PROPOSAL_REQUIREMENT_TRACEABILITY.md` ساخته شد.
3. Gapهای Production مثل Keycloak/Kong، AST SQL Validator، Connector Agent، ۲۰ Gold Test واقعی، SBOM و Observability استخراج شدند.
4. تست‌های Backend و Frontend برای مسیرهای حساس افزایش یافتند.

## بازبینی دوم و تکمیل تخصصی

در بازبینی دوم، علاوه بر موارد قبلی، این اصلاحات انجام شد:

- کنترل `X-API-Key` در مسیر تولید گزارش و ثبت `api_key_id` و `api_key_prefix`.
- کنترل محدودیت منطقه کاربر (`REGION_SCOPE_DENIED`).
- کنترل Quota روزانه/ماهانه کاربر و Tenant، سقف هزینه و سقف Token.
- جلوگیری از کسر اعتبار تکراری با idempotency/replay check بر اساس Ledger reference.
- صفحه واقعی درخواست گزارش در Frontend با React Hook Form + Zod به جای Blueprint عمومی.
- تست‌های Backend برای Token Estimate، Region Scope و API Key نامعتبر.
- تست‌های Frontend برای Permission Guard و Token Estimate.

لیست کامل کارهای باقی‌مانده در `docs/REMAINING_WORK_REGISTER.md` ثبت شد.
