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
