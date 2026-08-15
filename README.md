# سامانه هوشمند گزارش‌ساز و NL2SQL

پیاده‌سازی پایه و قابل توسعه مطابق RFP اصلی برای چهار محیط کاربری:

1. پنل مالک سامانه
2. پنل مدیر نرم‌افزار
3. رابط کاربر داخل نرم‌افزار On-Premise مانند بهساز
4. کنسول فنی Connector و عملیات

این پروژه از Python/FastAPI، React/Vite/TypeScript، PostgreSQL، Alembic، Docker و Git استفاده می‌کند.

## ساختار پروژه

```text
backend/                 FastAPI + SQLAlchemy + Alembic
  app/api/v1/endpoints   APIهای پنل‌ها و قرارداد NL2SQL
  app/models             مدل‌های داده PostgreSQL
  app/schemas            قراردادهای Pydantic
  app/services           Audit، Bootstrap، Knowledge، NL2SQL Stub
  alembic                Migrationها
frontend/                React + Vite + TypeScript با UI راست‌به‌چپ فارسی
docs/RFP_MAPPING.md      نگاشت RFP به اجزای پیاده‌سازی
docker-compose.yml       PostgreSQL، Redis، Backend، Frontend و Keycloak اختیاری
```


## معماری تمیزتر (Clean Architecture)

پس از بازبینی، ساختار پروژه از حالت صرفاً Router/Page محور به سمت معماری لایه‌ای اصلاح شد:

- Backend:
  - `backend/app/api`: فقط Adapterهای HTTP و Dependencyها
  - `backend/app/application`: Use Case، Port، Unit of Work Protocol و Application Error
  - `backend/app/infrastructure`: Repositoryهای SQLAlchemy و Unit of Work واقعی
  - `backend/app/domain`: مفاهیم دامنه مستقل از Framework
- Frontend:
  - `frontend/src/app`: Composition Root
  - `frontend/src/layouts`: Layout عملیاتی محصول
  - `frontend/src/routes/pageRegistry.ts`: کاتالوگ ۴۵ صفحه عملیاتی
  - `frontend/src/features`: API و مدل هر قابلیت کسب‌وکاری
  - `frontend/src/shared`: HTTP Client، Config، Components و UI مشترک
  - `frontend/src/pages`: صفحات پایلوت/سازگاری قبلی

نقشه ۴۵ صفحه در `docs/PAGE_MAP_45.md` و گزارش دقیق بخش‌های نیازمند حرفه‌ای‌سازی در `docs/ARCHITECTURE_REVIEW.md` آمده است.

## اجرای سریع با Docker

```bash
docker compose up --build
```

سپس:

- Frontend: <http://localhost:5173>
- Backend health: <http://localhost:8000/health>
- OpenAPI: <http://localhost:8000/docs>
- PostgreSQL: `localhost:5432`

## کاربران Seed برای توسعه

در شروع برنامه، داده پایلوت بهساز و کاربران زیر ساخته می‌شوند:

| کاربر | رمز | نقش |
|---|---|---|
| `owner` | `OwnerChangeMe!12345` | مالک سامانه |
| `software-admin` | `AdminChangeMe!12345` | مدیر نرم‌افزار، MFA نمونه با کد `123456` |
| `report-user` | `UserChangeMe!12345` | کاربر گزارش |

## اجرای محلی Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

برای اتصال محلی بدون Docker مقدار `DATABASE_URL` را تنظیم کنید. در حالت توسعه `AUTO_CREATE_DB=true` و `SEED_DEMO_DATA=true` می‌تواند جداول و داده نمونه را بسازد.

## اجرای محلی Frontend

```bash
cd frontend
npm install
npm run dev
```

در صورت نیاز:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

## نمونه درخواست قرارداد اصلی NL2SQL

```bash
curl -X POST http://localhost:8000/api/v1/reports/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "request_id":"11111111-1111-4111-8111-111111111111",
    "software_id":"behsaz",
    "software_version":"12.4.0",
    "user_id":"user-1025",
    "question":"آخرین پرونده‌های ماده ۱۰۰ را نشان بده",
    "access_context":{"organization":"municipality-01","region":["1","2"],"roles":["report-user"],"scopes":["commission100.read"]},
    "locale":"fa-IR",
    "timezone":"Asia/Tehran"
  }'
```

## تست‌ها

```bash
cd backend
pytest
```

## نکات طراحی

- خروجی مرکزی فقط SQL پارامتری، Parameters، Display Spec، Confidence، Audit ID و Policy است.
- داده خام گزارش به سرویس مرکزی ارسال یا ذخیره نمی‌شود.
- Secretها، Tokenها و Connection Stringها در Audit Log مخفی می‌شوند.
- Chain-of-Thought داخلی مدل نمایش داده نمی‌شود.
- برای پایلوت، سرویس NL2SQL به‌صورت Rule-based Stub پیاده‌سازی شده تا بعداً به Model Router واقعی متصل شود.

جزئیات کامل نگاشت RFP در `docs/RFP_MAPPING.md` آمده است.

## مرحله حرفه‌ای‌سازی دسترسی، گردش‌کار و Token Accounting

در مرحله بعدی، موارد زیر به ساختار اضافه شد:

- Backend:
  - `AccessControlService` برای ارزیابی Tenant، نرم‌افزار، کاربر، Scope، Permission، Policy Hash و Access Fingerprint.
  - `TokenAccountingService` برای تخمین Token، محاسبه هزینه بر اساس Tariff فعال، کنترل اعتبار کیف و ثبت Ledger غیرقابل‌ویرایش.
  - Use Caseهای عملیاتی برای RBAC Matrix، مجوز مؤثر، Audit Timeline، عملیات Wallet با Idempotency-Key، Rotation کلید API، Policy Sync کانکتور و اجرای Regression تست‌های طلایی.
  - Middleware مشترک `X-Request-ID`، `X-Correlation-ID` و `Idempotency-Key`.
- Frontend:
  - `PermissionGuard` و Session Store مبتنی بر Zustand برای کنترل دسترسی صفحات.
  - Hookهای Feature واقعی: `useTenantManagement`, `useKnowledgeWorkflow`, `useSnapshotPublish`, `useRequestMonitoring`, `useConnectorHealth`.
  - پنل `TokenAccountingPanel` برای نمایش تخمین Prompt/Completion Token، هزینه و مانده اعتبار پیش از درخواست گزارش.

در تولید نهایی، Guardها باید به JWT/Keycloak و ماتریس RBAC Backend متصل شوند و Token Accounting فقط مقدار قطعی Backend را مبنا قرار دهد.

## تکمیل مرحله دسترسی، Token Accounting و اقدام‌های پروپوزال

در مرحله جدید، مسیر درخواست گزارش از نظر امنیت و مالی حرفه‌ای‌تر شد:

- Access Control مرکزی برای Tenant، نرم‌افزار، کاربر، Scope، Role، منطقه، `policy_hash` و `access_fingerprint`
- API تخمین هزینه و Token: `POST /api/v1/reports/token-estimate`
- محاسبه Prompt/Completion Token و هزینه در `POST /api/v1/reports/generate`
- کنترل اعتبار کیف و ثبت مصرف در `WalletLedger`
- پشتیبانی از `X-API-Key` برای درخواست گزارش و ثبت Prefix در Audit
- Idempotency برای جلوگیری از کسر اعتبار تکراری
- Use Caseهای تکمیلی برای Tenant، RBAC Matrix، Audit Timeline، Wallet، API Key Rotation، Connector Policy Sync و Gold Test Regression
- Guard سطح دسترسی در Frontend و پنل تخمین Token/Cost برای صفحات گزارش

گزارش اقدام در `docs/PROPOSAL_ACTION_LOG.md` ثبت شده است.

## بازبینی دوم تخصصی و کارهای باقی‌مانده

در بازبینی دوم، علاوه بر کنترل دسترسی و Token Accounting، موارد زیر اضافه شد:

- اعتبارسنجی `X-API-Key` در مسیر گزارش و ثبت Prefix در Audit
- کنترل Region Scope و Quota روزانه/ماهانه کاربر و Tenant
- جلوگیری از کسر اعتبار تکراری با replay/idempotency check
- صفحه واقعی درخواست گزارش با React Hook Form + Zod
- تست Backend برای Token Estimate، API Key نامعتبر و Region Scope
- تست Frontend با Vitest برای Permission و Token Estimate

لیست تخصصی کارهای باقی‌مانده در `docs/REMAINING_WORK_REGISTER.md` آمده است.
