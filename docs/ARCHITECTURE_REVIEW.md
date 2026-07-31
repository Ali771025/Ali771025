# بازبینی حرفه‌ای معماری و بخش‌های نیازمند دقت بیشتر

این بازبینی با فرض کنارگذاشتن «بخش ربات / هسته NL2SQL» انجام شده و روی محصول، پنل‌ها، امنیت، داده و معماری نرم‌افزار تمرکز دارد.

## جمع‌بندی صریح

نسخه اولیه برای اسکلت محصول مناسب بود، اما برای سطح تخصصی و قابل نگهداری باید حرفه‌ای‌تر شود. مهم‌ترین ایراد، مخلوط‌شدن لایه‌ها بود: در Backend منطق Use Case داخل Routerها آمده بود و در Frontend صفحات همزمان مسئول UI، State، API Call و Mapping داده بودند. برای شروع اصلاح، ساختار Clean Architecture اضافه شد و چند جریان کلیدی از Router/Page جدا شد.

## اولویت اصلاح به جز بخش ربات

### 1. معماری Backend و مرزبندی لایه‌ها — بسیار مهم

مشکل قبلی:

- `endpoints/software.py` شامل منطق تجاری، اعتبارسنجی، Audit، Persistence و HTTP Error بود.
- SQLAlchemy Model نقش Domain Model و Persistence Model را همزمان بازی می‌کرد.
- Use Case مستقل و قابل تست وجود نداشت.
- خطاهای کسب‌وکاری مستقیماً با `HTTPException` مدل شده بودند.

اصلاح انجام‌شده در این مرحله:

- اضافه‌شدن لایه‌های زیر:
  - `backend/app/application`: Use Caseها، Portها و Exceptionهای Application
  - `backend/app/infrastructure`: Adapterهای SQLAlchemy و Unit of Work
  - `backend/app/domain`: نقطه شروع Domain Layer مستقل از Framework
- جریان‌های کلیدی زیر از Router جدا و به Use Case منتقل شدند:
  - ایجاد نرم‌افزار
  - ایجاد نسخه نرم‌افزار
  - بارگذاری سند دانش
  - استانداردسازی دانش
  - انتشار Snapshot
- اضافه‌شدن `ApplicationError` و Error Handler مرکزی برای تبدیل خطاهای Use Case به HTTP Response.
- اضافه‌شدن `ActorContext` برای عبور metadata کاربر بدون وابستگی Use Case به FastAPI.

باقی‌مانده برای حرفه‌ای‌سازی کامل:

- جداکردن کامل Domain Entity از SQLAlchemy ORM.
- انتقال همه عملیات `owner`, `auth`, `connector`, `quality`, `finance` به Use Caseهای مستقل.
- اضافه‌کردن Repository Port برای User، Tenant، Billing، Connector و Audit Query.
- اضافه‌کردن Transaction Boundary استاندارد با Context Manager برای Unit of Work.

### 2. Tenant Isolation و کنترل Scope — بسیار مهم

مشکل فعلی:

- بخشی از Queryها هنوز فقط براساس نقش کاربر فیلتر می‌شوند و Tenant/Scope به‌صورت سراسری enforce نشده است.
- کاربر مدیر نرم‌افزار نباید بتواند همه نرم‌افزارها، درخواست‌ها یا API Keyهای خارج از Tenant/Scope خود را ببیند.

اقدام پیشنهادی:

- ایجاد `AccessPolicyService` در Application Layer.
- اعمال فیلتر Tenant/Software Scope در Repository سطح پایین.
- اضافه‌کردن تست‌های امنیتی برای Cross-Tenant Access.

### 3. امنیت Auth و Session Management — بسیار مهم

مشکل فعلی:

- MFA و Password Reset در حد Stub توسعه هستند.
- Refresh Token در Ledger/Session واقعی ذخیره و ابطال نشده است.
- CAPTCHA و تشخیص ورود مشکوک فقط در قرارداد آمده و کامل نشده است.

اقدام پیشنهادی:

- اتصال production به Keycloak/OIDC.
- ذخیره Hash Refresh Token در `user_sessions`.
- ابطال نشست‌ها هنگام تغییر رمز یا Reset.
- Rate Limit، CAPTCHA و Lockout Policy.
- MFA واقعی با TOTP و Recovery Code Hash شده.

### 4. Frontend Clean Architecture — بسیار مهم

مشکل قبلی:

- Page Componentها مستقیم `fetch/api` می‌زدند.
- نوع‌ها، API Client، State و UI در یک فایل مخلوط بود.
- تفکیک `feature`, `entity`, `shared`, `app` وجود نداشت.

اصلاح انجام‌شده در این مرحله:

- اضافه‌شدن ساختار Feature-based Clean Frontend:
  - `frontend/src/shared/api/httpClient.ts`
  - `frontend/src/shared/config/env.ts`
  - `frontend/src/shared/ui/*`
  - `frontend/src/features/auth/api/authApi.ts`
  - `frontend/src/features/owner/api/ownerApi.ts`
  - `frontend/src/features/software-admin/api/softwareAdminApi.ts`
  - `frontend/src/features/reporting/api/reportApi.ts`
  - `frontend/src/features/connector/api/connectorApi.ts`
  - `frontend/src/app/App.tsx`
- `lib/api.ts` فقط برای سازگاری به shared client re-export می‌کند.

باقی‌مانده برای حرفه‌ای‌سازی کامل:

- انتقال Form State و workflowها به Hookهای Feature مثل `useLogin`, `useSoftwareCatalog`, `useKnowledgeWorkflow`.
- جداکردن UI خالص از Smart Containerها.
- اضافه‌کردن React Query یا RTK Query برای Cache، Mutation و Error State.
- اضافه‌کردن Route-based layout با `react-router` و Guardهای Role/Permission.
- اضافه‌کردن تست Component و Integration با Vitest/Testing Library.

### 5. Billing، Wallet و Payment — مهم

مشکل فعلی:

- مدل داده و endpointهای اولیه وجود دارد، اما Ledger double-entry، reconciliation و idempotency کامل نیست.

اقدام پیشنهادی:

- طراحی Ledger غیرقابل تغییر.
- Idempotency Key برای پرداخت و Callback.
- State Machine برای Payment.
- گزارش مغایرت مالی و Adjustment کنترل‌شده.

### 6. Audit، Retention و Redaction — مهم

مشکل فعلی:

- Redaction پایه وجود دارد، اما سیاست Retention، سطح حساسیت، export کنترل‌شده و chain integrity کامل نیست.

اقدام پیشنهادی:

- تعریف `RedactionPolicy` per Tenant.
- Hash Chain یا امضای رخدادهای Audit حساس.
- Retention Job و Legal Hold.
- جلوگیری از نمایش Secret در همه خروجی‌ها با تست خودکار.

### 7. Connector Operations — مهم

مشکل فعلی:

- ثبت، Heartbeat و Validate/Execute اسکلت دارد؛ اجرای واقعی DB و mTLS production کامل نیست.

اقدام پیشنهادی:

- Agent جداگانه برای نصب داخل شبکه مشتری.
- Policy Sync امضاشده.
- mTLS واقعی و Certificate Rotation.
- Allowlist دقیق View/Table و SQL AST Validator.
- ارسال فقط metadata و منع مطلق ارسال داده خام.

### 8. Observability و Background Jobs — متوسط تا مهم

اقدام پیشنهادی:

- OpenTelemetry برای FastAPI و Workerها.
- Structured Logging با Correlation ID.
- Queue واقعی با Celery/RQ/Arq.
- Dashboard سلامت زیرساخت با Probeهای واقعی.

## استاندارد هدف برای ادامه توسعه

### Backend

```text
api/               HTTP adapters, auth dependency, response mapping
application/       use cases, ports, DTO commands, application errors
domain/            domain entities, value objects, policies, invariants
infrastructure/    SQLAlchemy repositories, UoW, external gateways
models/            ORM persistence models until full domain split
schemas/           API contracts only
```

قاعده: Router نباید تصمیم کسب‌وکاری بگیرد. Router فقط payload را validate، actor context را بسازد، Use Case را صدا بزند و response برگرداند.

### Frontend

```text
app/               composition root, providers, routing
pages/             page composition only
features/          workflows/use cases per business capability
entities/          domain-facing frontend models
shared/api         http client and transport concerns
shared/ui          reusable presentational components
shared/config      env and static config
```

قاعده: Page نباید مستقیم `fetch` بزند یا mapping قرارداد API را بداند؛ Feature API/Hook باید این مسئولیت را بگیرد.
