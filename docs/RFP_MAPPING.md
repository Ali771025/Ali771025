# نگاشت RFP سامانه هوشمند گزارش‌ساز و NL2SQL به پیاده‌سازی

> این مستند فقط مربوط به «سامانه هوشمند گزارش‌ساز و NL2SQL» است و با RFP مربوط به Learning Center ترکیب نشده است.

## محیط‌های کاربری

| محیط | Frontend | Backend Prefix | هدف |
|---|---|---|---|
| صفحات عمومی | `frontend/src/pages/public` | `/api/v1/auth`, `/api/v1/notifications` | ورود، MFA، بازیابی رمز، پروفایل، اعلان‌ها |
| پنل مالک سامانه | `frontend/src/pages/owner` | `/api/v1/owner` | داشبورد کلان، Tenant، مدیران، RBAC، مالی، مدل‌ها، Audit، سلامت زیرساخت |
| پنل مدیر نرم‌افزار | `frontend/src/pages/software` | `/api/v1/software-admin` | نرم‌افزار، نسخه، دانش، Snapshot، کاربران، API Key، مانیتورینگ، کیفیت، Gold Test |
| رابط On-Premise مثل بهساز | `frontend/src/pages/onprem` | `/api/v1/reports` | درخواست گزارش، ابهام‌زدایی، نمایش نتیجه محلی، بازخورد |
| کنسول Connector | `frontend/src/pages/connector` | `/api/v1/connectors` | ثبت Connector، سلامت، اعتبارسنجی و اجرای محلی SQL |

## مدل داده اصلی

مدل‌ها در `backend/app/models/domain.py` تعریف شده‌اند و Migration اولیه در `backend/alembic/versions/202607310001_initial_schema.py` قرار دارد.

- `Tenant`, `User`, `Role`, `UserSession`
- `SoftwareProduct`, `SoftwareVersion`
- `KnowledgeDocument`, `KnowledgeSnapshot`, `SchemaRelation`
- `APIKey`, `AIModel`, `ModelPolicy`
- `Tariff`, `WalletLedger`, `Payment`
- `ReportRequest`, `AuditLog`, `Feedback`, `Recipe`, `GoldTest`
- `Connector`, `BackgroundJob`

## قرارداد اصلی API گزارش‌ساز

Endpoint: `POST /api/v1/reports/generate`

- ورودی مطابق RFP: `request_id`, `software_id`, `software_version`, `user_id`, `question`, `access_context`, `locale`, `timezone`
- خروجی‌های پشتیبانی‌شده:
  - `success`: SQL پارامتری، Parameters، Display Spec، Confidence، Audit ID و Policy
  - `needs_clarification`: سؤال ابهام‌زدایی و گزینه‌ها
  - `rejected`: علت رد کنترل‌شده

نکته امنیتی: نتیجه خام اجرای SQL در شبکه مشتری باقی می‌ماند و در قرارداد مرکزی ارسال نمی‌شود. endpoint `/api/v1/reports/execution-result` فقط متادیتای اجرا را می‌پذیرد.

## اولویت‌ها

### اولویت اول؛ پایلوت

پیاده‌سازی شده به‌صورت پایه و قابل توسعه:

- ورود و احراز هویت: `/auth/login`, `/auth/mfa/verify`
- داشبورد مدیر نرم‌افزار: `/software-admin/dashboard`
- تعریف نرم‌افزار و نسخه: `/software-admin/software`, `/software-admin/versions`
- بارگذاری/مدیریت دانش و استانداردسازی: `/software-admin/knowledge`, `/software-admin/knowledge/standardize`
- انتشار Snapshot و Rollback: `/software-admin/snapshots/publish`, `/software-admin/snapshots/{id}/rollback`
- کاربران و API Key: `/software-admin/users`, `/software-admin/api-keys`
- مانیتورینگ و جزئیات درخواست: `/software-admin/requests`, `/software-admin/requests/{id}`
- تست طلایی: `/software-admin/gold-tests`
- فرم درخواست گزارش On-Premise: `/reports/generate`

### اولویت دوم؛ پیش‌تولید

اسکلت و API اولیه آماده است:

- پنل مالک، مدیران، RBAC، Tenant، تعرفه، کیف اعتبار، Model Router، Recipe، کیفیت سه‌گانه، Audit، Connector، گزارش‌های مدیریتی

### اولویت سوم؛ تحویل نهایی

اسکلت داده و مسیر توسعه آماده است:

- پرداخت آنلاین، تطبیق مالی، داشبورد زیرساخت، Backup/Restore، هشدارها، Retention/Redaction، UAT و Regression کامل

## ملاحظات امنیتی

- Token، API Key کامل، Credential و Connection String در Audit با `redact` مخفی می‌شوند.
- Secret کلید API فقط یک‌بار در پاسخ صدور کلید نمایش داده می‌شود.
- Chain-of-Thought داخلی مدل در هیچ endpoint ذخیره یا نمایش داده نمی‌شود.
- Connector فقط SQL خواندنی و دارای سقف ردیف را می‌پذیرد.
- اجرای واقعی SQL باید داخل شبکه مشتری انجام شود.
