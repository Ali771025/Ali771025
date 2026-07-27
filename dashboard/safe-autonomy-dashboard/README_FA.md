# داشبورد مستقل عملیات پرواز — v0.1.0-dev1

داشبورد RTL برای کارشناس و مدیر پرواز با بک‌اند Python/FastAPI و فرانت‌اند React + Vite + TypeScript. این نسخه داده GPS/IMU تجمیع‌شده، تله‌متری، YOLO/Tracking، مسیرهای A*، سلامت ماژول‌ها، هشدارها و تحلیل حالت پرواز را با تأخیر کم نمایش می‌دهد و دارای چت مدل مشورتی و پنل کنترل نظارت‌شده است.

## قابلیت‌های اصلی

- دریافت پرتکرار UDP و رخداد قابل‌اعتماد TCP NDJSON
- پخش لحظه‌ای WebSocket با ticket یک‌بارمصرف و reconnect خودکار
- REST API، JWT/HMAC-SHA256، PBKDF2 و RBAC دو نقش
- SQLite در حالت WAL برای کاربر، هشدار، تله‌متری نمونه‌برداری‌شده، چت، intent و audit
- نمای عملیات، نقشه و مسیر جایگزین، استریم ویدیو/overlay ردیابی، هشدار و سلامت ماژول
- چت Ollama با پاسخ JSON بسته، fallback قطعی و سد محتوای کنترلی
- کنترل سطح‌بالا با precondition، idempotency، انقضا، تأیید دومرحله‌ای و adapter شبیه‌ساز/درگاه HMAC
- Docker Compose و پیکربندی مناسب Jetson AGX Orin 64GB

## اجرای توسعه

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn flight_dashboard.main:app --host 0.0.0.0 --port 8080 --reload
```

ترمینال دوم:

```bash
cd frontend
npm install
npm run dev
```

ترمینال سوم:

```bash
python tools/fixture_sender.py --hz 20 --fault-after 30
```

صفحه `http://localhost:5173` باز می‌شود. حساب‌های توسعه از `.env.example` خوانده می‌شوند: `expert / expert-dev` و `manager / manager-dev`. این مقادیر برای تولید مناسب نیستند.

## کنترل

در حالت پیش‌فرض `simulation`، همه کنترل‌ها همراه پیش‌شرط و ممیزی اجرا می‌شوند اما فرمانی به پهپاد واقعی نمی‌رسد. `HOLD`, `RESUME_MISSION`, `DISARM` با یک درخواست و عملیات بحرانی مانند `ARM`, `TAKEOFF`, `RETURN_TO_HOME`, `LAND`, `ABORT_MISSION` با درخواست کارشناس و تأیید جداگانه مدیر انجام می‌شوند.

برای سخت‌افزار، `DASH_CONTROL_MODE=gateway` فقط intent سطح‌بالا را به یک gateway مورداعتماد و امضاشده می‌فرستد. داشبورد raw actuator، setpoint، waypoint یا MAVLink تولید نمی‌کند.

## آزمون

```bash
pytest -q
cd frontend && npm run build
```

جزئیات: [معماری](docs/ARCHITECTURE_FA.md)، [پروتکل شبکه](docs/PROTOCOL_FA.md)، [استقرار Jetson](docs/JETSON_DEPLOYMENT_FA.md).

## وضعیت نسخه

این خروجی یک Developer Preview حرفه‌ای است. قبل از پرواز واقعی باید تست SITL/HIL، آزمون latency روی AGX، threat model، TLS، پشتیبان‌گیری دیتابیس و بازبینی مستقل ایمنی انجام شود.
