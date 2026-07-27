# یادداشت انتشار 0.6.0-dev1

این نسخه یک ارتقای سازگار با 0.5 برای تحلیل مأموریت و تضمین runtime است. خروجی‌ها همچنان پژوهشی و advisory هستند و هیچ PX4 publisher، actuator، setpoint یا waypoint-command به پروژه اضافه نشده است.

## ماژول‌های جدید

- `temporal_guard.py`: کنترل sequence، freshness، future timestamp، clock regression و skew
- `health_manager.py`: heartbeat و readiness ماژول‌های ضروری/اختیاری
- `dynamic_risk.py`: پیش‌بینی محدود trackها و لایه ریسک پویا
- `route_revalidation.py`: پیشرفت، cross-track، corridor risk و cooldown
- `energy_model.py`: انرژی مسیر، reserve، صعود، avionics و باد
- `observability.py`: P50/P95/P99 و SLO با حافظه محدود
- `mission_assurance.py`: گیت نهایی `PASS/WARN/FAIL` و هش محتوایی
- `assurance_repository.py`: ذخیره شواهد جدید در migration شماره ۶

## API نسخه ۲

APIهای زمان، heartbeat/readiness، انرژی، revalidation، assurance و latency به FastAPI افزوده شده‌اند. API تحلیل مسیر فیلدهای کنترل/عملگر را رد می‌کند.

## اصلاح رگرسیون

سناریوهای پایه دیگر به SQLite development داخل ZIP وابسته نیستند و تست‌ها به‌صورت پیش‌فرض in-memory اجرا می‌شوند؛ در نتیجه ناقص‌بودن فایل‌های WAL در بسته نمی‌تواند تست سناریو را خراب کند.

## وضعیت اعتبارسنجی

- تست‌های unit/integration: ۷۸ مورد؛ هر ۷۸ مورد با وابستگی اختیاری API موفق
- migrationها: ۶ نسخه
- سیم‌کشی ماشین‌خوان: schema 2.0
- معیار سخت‌افزاری Jetson: تا زمان اجرای واقعی روی AGX 64GB اندازه‌گیری نشده است
