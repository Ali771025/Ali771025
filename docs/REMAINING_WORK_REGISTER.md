# لیست تخصصی کارهای باقی‌مانده و وضعیت اجرا

> بررسی دوباره انجام شد. PDF پروپوزال از repo بازیابی و خوانده شد؛ این لیست بر اساس متن PDF، ساختار ۴۵ صفحه و کد فعلی تهیه شده است.

## انجام‌شده در این مرحله

| حوزه | اقدام | وضعیت |
|---|---|---|
| کنترل دسترسی گزارش | اعتبارسنجی Tenant/Software/User/Scope/Region و تولید `policy_hash` و `access_fingerprint` | انجام شد |
| API Key گزارش | پشتیبانی `X-API-Key`، اعتبارسنجی Hash، وضعیت، انقضا، Scope و ثبت Prefix در Audit | انجام شد |
| Token Accounting | تخمین Prompt/Completion Token، تعرفه، Cost، Wallet Balance و Ledger مصرف | انجام شد |
| Idempotency | جلوگیری از کسر اعتبار تکراری برای request/idempotency تکراری | انجام شد |
| Quota | کنترل Daily/Monthly Quota کاربر و Tenant، سقف هزینه و سقف Token | انجام شد |
| Frontend Guard | کنترل Permission هر صفحه با `PermissionGuard` | انجام شد |
| صفحه واقعی درخواست گزارش | فرم React Hook Form + Zod، تخمین Token، تولید گزارش و نمایش نتیجه | انجام شد |
| تست Backend | تست موفقیت، خروج از Scope، تخمین Token، Region Scope و API Key نامعتبر | انجام شد |
| تست Frontend | تست Permission و Token estimate utility با Vitest | انجام شد |

## باقی‌مانده سطح Production

| اولویت | کار باقی‌مانده | توضیح فنی |
|---|---|---|
| P0 | اتصال Auth به Keycloak/OIDC واقعی | JWT فعلی داخلی است؛ باید Realm/Client/Role Mapper و Refresh Token امن نهایی شود. |
| P0 | Enforcement کامل Tenant در همه Queryهای مدیریتی | برخی صفحات مالک/مدیر هنوز query عمومی دارند و باید Repository-level tenant filter بگیرند. |
| P0 | ذخیره و Replay Protection کامل Idempotency | فعلاً بر اساس Ledger reference برای مالی/گزارش کنترل شده؛ جدول مستقل idempotency برای همه Mutationها لازم است. |
| P0 | SQL Validator واقعی با AST | Validator فعلی rule-based است؛ باید parser برای T-SQL/Postgres و allowlist جدول/ستون اضافه شود. |
| P0 | Connector Agent واقعی | کنسول مرکزی و endpoint هست؛ agent نصب‌شونده داخل شبکه مشتری باید جداگانه ساخته شود. |
| P1 | پیاده‌سازی اختصاصی همه ۴۵ صفحه | اکنون page registry و shell آماده است؛ برخی صفحه‌ها هنوز generic operations page هستند. |
| P1 | State Machine انتشار Snapshot | باید draft/review/approved/published/rollback با approval policy کامل شود. |
| P1 | Workflow تعارض و Comment/Reviewer | Conflict Center در registry هست؛ backend workflow کامل نیاز دارد. |
| P1 | Ledger مالی Double-entry | Ledger فعلی immutable است ولی double-entry accounting و reconciliation کامل نیست. |
| P1 | Audit Hash Chain | Redaction هست؛ tamper-evident chain/signature برای رخدادهای حساس لازم است. |
| P1 | Job Queue واقعی | BackgroundJob مدل دارد؛ Celery/RQ/Arq و progress websocket لازم است. |
| P2 | Monaco Editor امن | به علت advisoryهای npm فعلاً نصب نشده؛ بعد از نسخه امن برای SQL/Markdown editor اضافه شود. |
| P2 | React Router امن | به علت advisoryهای npm فعلاً history API سبک استفاده شده؛ پس از رفع advisory جایگزین شود. |
| P2 | Component Tests کامل | تست پایه اضافه شده؛ تست همه فرم‌های حساس و Guardها با Testing Library لازم است. |

## معیار پذیرش مرحله بعد

1. هیچ API مدیریتی بدون Tenant/Scope filter نباشد.
2. هر Mutation حساس `Idempotency-Key` اجباری و replay-safe داشته باشد.
3. درخواست گزارش بدون اعتبار، بدون Scope، با Region غیرمجاز یا API Key نامعتبر رد کنترل‌شده شود.
4. داده خام مشتری در هیچ response مرکزی و audit ذخیره نشود.
5. ۲۰ Gold Test اجباری قبل از Snapshot publish enforce شود.
