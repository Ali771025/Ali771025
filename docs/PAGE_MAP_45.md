# نقشه اجرایی ۴۵ صفحه عملیاتی

این فایل از `frontend/src/routes/pageRegistry.ts` استخراج شده و نقشه صفحه‌های نهایی سامانه گزارش‌ساز هوشمند و NL2SQL است.

| محیط | تعداد صفحه | هدف |
|---|---:|---|
| public | 4 | احراز هویت و امنیت حساب |
| owner | 15 | مدیریت کلان سامانه، مالی، مدل و زیرساخت |
| software-admin | 19 | مدیریت نرم‌افزار، دانش، نسخه، انتشار و کیفیت |
| on-premise | 4 | ثبت درخواست فارسی، نتیجه محلی و بازخورد |
| connector | 3 | راه‌اندازی و اجرای امن Connector |
| **جمع** | **45** | حدود ۳۵ تا ۴۵ صفحه عملیاتی |

## public

| # | Route | صفحه | اولویت | APIهای کلیدی |
|---:|---|---|---|---|
| 1 | `/auth/login` | ورود به سامانه | pilot | `POST /auth/login` |
| 2 | `/auth/mfa` | احراز هویت دومرحله‌ای | pilot | `POST /auth/mfa/verify`<br>`POST /auth/mfa/resend` |
| 3 | `/auth/forgot-password` | فراموشی رمز عبور | pilot | `POST /auth/password/forgot`<br>`POST /auth/password/reset` |
| 4 | `/auth/profile-security` | پروفایل و امنیت حساب | pilot | `GET /auth/profile`<br>`PATCH /auth/profile`<br>`POST /auth/password/change` |

## owner

| # | Route | صفحه | اولویت | APIهای کلیدی |
|---:|---|---|---|---|
| 1 | `/owner/dashboard` | داشبورد کلان مالک | pre-production | `GET /owner/dashboard` |
| 2 | `/owner/tenants` | سازمان‌ها و Tenantها | pre-production | `GET /owner/tenants`<br>`POST /owner/tenants`<br>`PATCH /owner/tenants/{id}` |
| 3 | `/owner/managers` | مدیران نرم‌افزار | pre-production | `GET /owner/managers`<br>`POST /owner/managers`<br>`POST /owner/managers/{id}/reset-password` |
| 4 | `/owner/roles` | نقش‌ها و مجوزهای مدیریتی | pre-production | `GET /owner/roles`<br>`POST /owner/roles` |
| 5 | `/owner/software` | نظارت بر نرم‌افزارها | pre-production | `GET /owner/software` |
| 6 | `/owner/ai-models` | مدل‌های هوش مصنوعی و Model Router | pre-production | `GET /owner/models`<br>`POST /owner/models`<br>`POST /owner/models/{id}/test` |
| 7 | `/owner/tariffs` | تعرفه‌ها | pre-production | `GET /owner/tariffs`<br>`POST /owner/tariffs` |
| 8 | `/owner/wallets` | کیف اعتبار | pre-production | `GET /wallets`<br>`POST /owner/wallet-ledger` |
| 9 | `/owner/payments` | پرداخت و تطبیق مالی | final | `GET /payments`<br>`POST /owner/payments` |
| 10 | `/owner/financial-reports` | گزارش‌های مالی | final | `GET /owner/reports?type=financial` |
| 11 | `/owner/usage-reports` | گزارش‌های مصرف | pre-production | `GET /owner/reports?type=usage` |
| 12 | `/owner/audit-log` | Audit Log | pre-production | `GET /owner/audit-logs` |
| 13 | `/owner/security-events` | رخدادهای امنیتی | pre-production | `GET /owner/audit-logs?event_type=security` |
| 14 | `/owner/infrastructure-health` | سلامت زیرساخت و هشدارها | final | `GET /owner/infrastructure/health` |
| 15 | `/owner/settings` | تنظیمات سامانه | final | `GET /settings`<br>`PATCH /settings` |

## software-admin

| # | Route | صفحه | اولویت | APIهای کلیدی |
|---:|---|---|---|---|
| 1 | `/software-admin/dashboard` | داشبورد مدیر نرم‌افزار | pilot | `GET /software-admin/dashboard` |
| 2 | `/software-admin/software-definition` | تعریف نرم‌افزار | pilot | `POST /software-admin/software` |
| 3 | `/software-admin/versions` | مدیریت نسخه‌ها | pilot | `GET /software-admin/software/{id}/versions`<br>`POST /software-admin/versions` |
| 4 | `/software-admin/knowledge-repository` | مخزن دانش | pilot | `GET /software-admin/knowledge`<br>`POST /software-admin/knowledge` |
| 5 | `/software-admin/document-editor` | ویرایشگر سند | pilot | `GET /software-admin/knowledge/{id}`<br>`PATCH /software-admin/knowledge/{id}`<br>`GET /software-admin/knowledge/{id}/diff` |
| 6 | `/software-admin/knowledge-standardization` | استانداردسازی دانش | pilot | `POST /software-admin/knowledge/standardize`<br>`GET /jobs/{id}` |
| 7 | `/software-admin/conflicts` | مرکز تعارض‌ها | pilot | `GET /conflicts`<br>`POST /conflicts/{id}/resolve` |
| 8 | `/software-admin/schema-graph` | Schema Graph | pilot | `GET /schema-graph/nodes`<br>`GET /schema-graph/edges`<br>`POST /schema-graph/validate-path` |
| 9 | `/software-admin/snapshots` | Snapshot و انتشار | pilot | `POST /software-admin/snapshots/publish`<br>`POST /software-admin/snapshots/{id}/rollback` |
| 10 | `/software-admin/users` | کاربران نرم‌افزار | pilot | `GET /software-admin/users`<br>`POST /software-admin/users` |
| 11 | `/software-admin/user-roles` | نقش و دسترسی کاربران | pre-production | `GET /roles`<br>`POST /software-admin/user-roles` |
| 12 | `/software-admin/api-keys` | API Keyها | pilot | `GET /software-admin/api-keys`<br>`POST /software-admin/api-keys`<br>`POST /software-admin/api-keys/{id}/revoke` |
| 13 | `/software-admin/consumption-quotas` | مصرف و سهمیه | pre-production | `GET /software-admin/consumption` |
| 14 | `/software-admin/requests` | مانیتورینگ درخواست‌ها | pilot | `GET /software-admin/requests`<br>`GET /software-admin/requests/{id}` |
| 15 | `/software-admin/quality-evaluation` | ارزیابی کیفیت | pre-production | `POST /software-admin/quality/reviews` |
| 16 | `/software-admin/cache-recipes` | Cache و Recipe | pre-production | `GET /software-admin/recipes`<br>`POST /software-admin/recipes` |
| 17 | `/software-admin/gold-tests-lab` | تست طلایی و محیط آزمایش | pilot | `GET /software-admin/gold-tests`<br>`POST /software-admin/gold-tests`<br>`POST /software-admin/gold-tests/{id}/run` |
| 18 | `/software-admin/model-policy` | سیاست مدل | pre-production | `POST /software-admin/model-policies` |
| 19 | `/software-admin/connectors` | Connectorها و تنظیمات نرم‌افزار | pre-production | `GET /connectors` |

## on-premise

| # | Route | صفحه | اولویت | APIهای کلیدی |
|---:|---|---|---|---|
| 1 | `/on-premise/report-request` | فرم درخواست گزارش داخل بهساز | pilot | `POST /reports/token-estimate`<br>`POST /reports/generate` |
| 2 | `/on-premise/clarification` | فرم رفع ابهام | pilot | `POST /reports/generate` |
| 3 | `/on-premise/results` | نمایش نتیجه گزارش | pilot | `POST /reports/execution-result` |
| 4 | `/on-premise/feedback` | بازخورد کاربر | pilot | `POST /reports/feedback` |

## connector

| # | Route | صفحه | اولویت | APIهای کلیدی |
|---:|---|---|---|---|
| 1 | `/connector/dashboard` | داشبورد Connector | pre-production | `GET /connectors/{id}/health` |
| 2 | `/connector/setup-wizard` | Wizard راه‌اندازی Connector | pre-production | `POST /connectors/register` |
| 3 | `/connector/local-validator` | Validator محلی | pre-production | `POST /connectors/{id}/execute` |

## الزامات مشترک پیاده‌سازی

- Breadcrumb، عنوان، توضیح، انتخاب سازمان/نرم‌افزار/نسخه، جست‌وجو، فیلتر پیشرفته، مرتب‌سازی، Server-side Pagination و تعیین Rows Per Page.
- Multi-select، عملیات گروهی، Export مجاز، Loading/Empty/Error State، تأیید دومرحله‌ای عملیات حساس، نمایش مجوز مؤثر، Last Updated و Request ID در خطا.
- همه Mutationهای حساس باید `X-Request-ID`، `X-Correlation-ID` و `Idempotency-Key` داشته باشند.
- داده خام گزارش مشتری، Secretها، Tokenها، Connection String و Chain-of-Thought نباید نمایش یا ذخیره شوند.
- درخواست گزارش قبل از تولید نهایی باید `POST /reports/token-estimate` را برای تخمین Prompt/Completion Token، هزینه و مانده کیف فراخوانی کند؛ مقدار قطعی پس از تولید در Wallet Ledger Backend ثبت می‌شود.
