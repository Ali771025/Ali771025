# گزارش جامع باگ‌های دو پروژه Safe Autonomy

این گزارش پس از اکسترکت کامل هر دو پروژه (safe-autonomy-dashboard v0.1.0-dev1 و safe-autonomy-mvp v0.6.0-dev1) و بررسی خط به خط کد منبع، تست‌ها، مایگریشن‌ها، Dockerfileها و فرانت‌اند تهیه شده است.

وضعیت تست‌ها:
- **Dashboard**: 7 تست پاس شد (backend) / TypeScript تایپ‌چک پاس شد
- **MVP**: 78 تست پاس شد

با وجود پاس شدن تمام تست‌ها، باگ‌های منطقی، امنیتی، استقراری و لکه‌های کیفیت زیر یافت شد که تست‌ها آن‌ها را پوشش نمی‌دهند.

---

## فهرست

1. پروژه ۱: Safe Autonomy Dashboard
2. پروژه ۲: Safe Autonomy MVP (هسته)
3. مشکلات مشترک / فرآیندی

---

# پروژه ۱: safe-autonomy-dashboard (v0.1.0-dev1)

## D1 🔴 بحرانی — درگاه ingest (UDP/TCP) کاملاً بدون احراز هویت است

**فایل**: `backend/src/flight_dashboard/ingest.py`, `main.py`, `deploy/docker-compose.yml`

پورت‌های UDP/15010 و TCP/15015 مستقیماً از FastAPI/asyncio باز می‌شوند و **هیچ** اعتبارسنجی منبع (IP allow-list، HMAC، توکن یا گواهی) ندارند. هر کسی که به شبکه دسترسی داشته باشد می‌تواند انولوپ‌های `alert`, `telemetry`, `vision`, `route_candidates` و ... تزریق کند و:
- هشدارهای CRITICAL جعلی به پنل ارسال کند،
- مقادیر تله‌متری را دستکاری کند،
- با جعل `route_candidates` در تصمیمات اپراتور اخلال ایجاد کند.

در `deploy/docker-compose.yml` هر دو پورت روی `0.0.0.0:` مپ شده‌اند:
```yaml
- "15010:15010/udp"
- "15011:15011/tcp"
```
(در حالی که پورت API بک‌اند با `127.0.0.1:8080:8080` درست بسته شده است.)

**پیشنهاد**: افزودن HMAC امضا روی انولوپ‌ها + allow-list IP در nginx/iptables + مپ کردن ingest روی `127.0.0.1` تا فقط از روی بریج داکر قابل دسترسی باشد.

---

## D2 🔴 بحرانی — JWT پیاده‌سازی‌شده دستی، هدر `alg` اعتبارسنجی نمی‌شود

**فایل**: `backend/src/flight_dashboard/auth.py`

تابع `decode_token` هدر JWT را می‌پارسد اما هرگز چک نمی‌کند که `alg` برابر `HS256` باشد. امضای HMAC با `settings.jwt_secret` محاسبه می‌شود، ولی اگر مهاجم بتواند هدر را طوری دستکاری کند که سرور به الگوریتم `none` یا کلید عمومی-خصوصی نامتقارن بیفتد (الگوی کلاسیک `alg=none`)، توکن جعلی قبول می‌شود. در حال حاضر پیاده‌سازی همیشه HMAC-SHA256 حساب می‌کند و هدر را نادیده می‌گیرد، لذا با اضافه کردن `alg: "none"` واقعاً شکست می‌خورد (چون `expected` با `signature` خالی برابر نمی‌شود) — ولی این قرارداد شکننده است و به صراحت چک نمی‌شود. همچنین `iat` و `nbf` اعتبارسنجی نمی‌شوند.

**پیشنهاد**: یا از کتابخانه استاندارد `PyJWT` استفاده شود یا حداقل `claims["alg"] == "HS256"` چک شود.

---

## D3 🟠 مهم — رمزهای پیش‌فرض در کد سخت‌کد شده و فرانت‌اند هم آن‌ها را پیش‌پر می‌کند

**فایل**: `backend/src/flight_dashboard/settings.py` و `frontend/src/App.tsx`

```python
expert_password: str = "expert-dev"
manager_password: str = "manager-dev"
jwt_secret: str = "development-only-change-this-secret"
```
و در App.tsx:
```ts
const [username, setUsername] = useState('expert')
const [password, setPassword] = useState('expert-dev')
```

اگر کاربر `.env` را کپی نکند یا در استقرار فراموش کند عوض کند، سامانه با رمزهای شناخته‌شده بالا می‌آید. اعتبارسنجی production فقط طول `jwt_secret` را چک می‌کند (`len < 32`) اما چیزی مانع استفاده از پسوردهای پیش‌فرض در حالت production نمی‌شود.

**پیشنهاد**: در حالت production، بالا آمدن با پسوردهای پیش‌فرض خطا دهد (`fail closed`).

---

## D4 🟠 مهم — endpoint لغو فرمان (`cancel`) هیچ کنترل نقشی ندارد

**فایل**: `backend/src/flight_dashboard/control.py` (متد `cancel`) و `main.py` خط `cancel_control_intent`

- هر کاربر احراز هویت‌شده (از جمله FLIGHT_EXPERT و FLIGHT_MANAGER) می‌تواند هر in-progress intent ای را لغو کند — حتی اگر درخواست‌کننده فرد دیگری بوده باشد.
- همچنین چک نمی‌شود که intent در وضعیت `EXPIRED` باشد (فقط `EXECUTED` و `CANCELLED` غیرقابل لغو هستند)، یعنی یک intent از قبل `EXECUTED` شده به درستی رد می‌شود اما یک intent `PENDING_APPROVAL` که زمانش سر رسیده همچنان لغو می‌شود (بی‌ضرر اما گیج‌کننده).
- مهم‌تر: **خود درخواست‌کننده** می‌تواند درخواستش را لغو کند که قابل قبول است، ولی انتظار می‌رود مانند approve نیاز به تفکیک نقش/کاربر داشته باشد (وگرنه مهاجم با دسترسی expert تنها می‌تواند با ارسال انبوه cancel عملیات را مختل کند).

---

## D5 🟠 مهم — Race condition / عدم همزمانی در تأیید و اجرای intent

**فایل**: `backend/src/flight_dashboard/control.py`

مسیر تأیید:
1. `approve()` رکورد را از دیتابیس می‌خواند،
2. وضعیت را به `APPROVED` تغییر می‌دهد،
3. سپس `await self.execute(intent_id)` را صدا می‌زند.

متد `execute` هم دوباره رکورد را می‌خواند و بعد از اجرا آن را به `EXECUTED` می‌برد. اگر دو درخواست تأیید همزمان برسند (یا درخواست approve بعد از expire شدن با تاخیر برسد)، به خاطر نبود قفل تراکنشی / به‌روزرسانی اتمیک، ممکن است فرمان **دوبار** به gateway ارسال شود. در حالت simulation دیده نمی‌شود اما در حالت `gateway` می‌تواند به ارسال تکراری ARM/TAKEOFF/LAND منجر شود.

`create_intent` هم از `idempotency_key` پشتیبانی می‌کند ولی approve/execute بلاایندمپوتنت نیست.

**پیشنهاد**: `UPDATE ... SET status='APPROVED' WHERE id=? AND status='PENDING_APPROVAL'` و چک `cursor.rowcount == 1`.

---

## D6 🟠 مهم — WebSocket بلیت (ticket) در دیکشنری in-memory نگه داشته می‌شود و چند نمونه worker آن را می‌شکند

**فایل**: `backend/src/flight_dashboard/main.py` (Runtime.ws_tickets)

- اگر بک‌اند با بیش از 1 worker اجرا شود (Dockerfile با `--workers 1` اجرا می‌شود که فعلاً امن است)، یا فرآیند ری‌استارت شود، بلیت‌ها از بین می‌روند.
- `issue_ws_ticket` پاکسازی را **فقط** در زمان صدور بلیت جدید انجام می‌دهد؛ اگر هیچ کاربری بلیت نگیرد بلیت‌های منقضی هرگز GC نمی‌شوند (نشت کوچک).
- کد WebSocket close `4401` کد معتبر استاندارد WebSocket نیست (بازه‌های مجاز: 1000، 3000-4999). کدهای 4000-4999 اپلیکیشن می‌توانند باشند ولی در برخی کلاینت‌ها (مثلاً مرورگرهای قدیمی) نادیده گرفته می‌شوند.

---

## D7 🟡 متوسط — health/readiness هاردکد `database: True`

**فایل**: `backend/src/flight_dashboard/main.py`
```python
def health_ready():
    return {"status": "ready", "database": True, ...}
```
حتی اگر دیتابیس بسته یا قفل باشد، `database=True` برمی‌گرداند. بنابراین healthcheck داکر هیچ‌گاه unhealthy نمی‌شود.

**پیشنهاد**: اجرای `SELECT 1` در یک timeout کوتاه.

---

## D8 🟡 متوسط — CORS به صورت پیش‌فرض در توسعه تمام مبداها را اجازه می‌دهد

`allow_origins=settings.cors_origins` لیست را از تنظیمات می‌گیرد. اگر `DASH_ALLOWED_ORIGINS=""` (رشته خالی در .env)، `cors_origins` لیست خالی `[]` می‌شود. در STARLETTE/FastAPI وقتی لیست خالی باشد، بسته به نسخه، ممکن است به معنی «رد همه» یا «قبول همه» تفسیر شود. بهتر بود `allow_origins=["*"]` وقتی اعتبارنامه‌ها `allow_credentials=True` هستند ممنوع شود (FastAPI خودش این را تشخیص می‌دهد ولی تست نشده).

---

## D9 🟡 متوسط — crc32 در پروتکل فقط در صورت وجود چک می‌شود؛ حذف فیلد به معنای عبور بدون اعتبارسنجی است

**فایل**: `backend/src/flight_dashboard/protocol.py`
```python
if envelope.crc32 and canonical_crc32(data) != envelope.crc32.lower():
    raise ProtocolError("crc32 mismatch")
```
از آنجا که `crc32` اختیاری است، هر کسی می‌تواند بدون امضا انولوپ بفرستد. این برای شبکه‌های خصوصی قابل قبول است اما در ترکیب با D1 (عدم احراز هویت ingest) مشکل جدی است. ضمناً CRC32 امضای امنیتی نیست.

---

## D10 🟡 متوسط — چت هوشمند: conversation_id در POST به کاربر متصل نیست

**فایل**: `backend/src/flight_dashboard/chat.py`

`ask()` هر conversation_id دلخواه را می‌پذیرد و پیام‌ها را تحت همان conversation_id با نام کاربر جاری ذخیره می‌کند. کاربر دیگر با همان conversation_id نمی‌تواند پیام‌های کاربر اول را بخواند (چرا که GET فیلتر `username=?` دارد) اما می‌تواند با حدس زدن/ارسال conversation_id، دو رشته چت مجزا روی یک conversation_id بسازد و جلسه همزمان را آلوده کند.

---

## D11 🟡 متوسط — `SampleLimiter` در درون async event loop با `time.monotonic` کار می‌کند که در صورت ساعت دیواری مشکلی نیست اما stateful است و در هر استارت ریست می‌شود

بیشتر یادداشت طراحی است تا باگ واقعی. اما اگر `udp_port=0` در تست پاس می‌شود، در production با `udp_host=0.0.0.0` در شرایط خاص ممکن است اجازه دهد تل‌متری با نرخ بالاتر از `telemetry_sample_hz` به دیتابیس برسد چرا که کلید `source` از روی انولوپ توسط مهاجم قابل جعل است (ترکیب با D1).

---

## D12 🟢 کوچک — frontend ذخیره توکن در sessionStorage و بلیت WS در query string

- توکن در `sessionStorage` ذخیره می‌شود که برای XSS آسیب‌پذیر است (HttpOnly cookie امن‌تر است).
- بلیت WS به‌صورت `?ticket=...` در URL ارسال می‌شود که معمولاً در لاگ‌های nginx/access_log ثبت می‌شود. با ۳۰ ثانیه TTL ریسک کمتر است اما بهتر بود در هدر یا در پیام اول بعد از برقراری WS ارسال شود.

---

## D13 🟢 کوچک — frontend دارای hardcoded "expert-dev" پیش‌فرض و حالت RTL بدون lang/ dir در index.html

`index.html` اصلی (و dist) `dir="rtl"` یا `lang="fa"` ندارند. تست‌های Dashboard.tsx: `actionLabels` شامل `DISARM, HOLD, RESUME_MISSION` هست ولی `DISARM` در CRITICAL_ACTIONS نیست و همچنان روی پنل نمایش داده می‌شود (فقط به تأیید ثانویه نیاز ندارد که خودش درست است ولی باید تصمیم اتخاذ شود که DISARM بحرانی محسوب شود یا نه).

---

# پروژه ۲: safe-autonomy-mvp (v0.6.0-dev1)

## M1 🔴 بحرانی — ترکیب ارتفاع فشارسنج بدون تصحیح آفست خانه (MSL ↔ local)

**فایل**: `src/safe_autonomy/sensor_fusion.py` (متد `_fused_altitude`)
```python
def _fused_altitude(self, gps: GpsSample) -> float:
    barometer = self._latest.get(SensorKind.BAROMETER)
    if not isinstance(barometer, BarometerSample):
        return gps.altitude_msl_m - self.home_altitude_m
    gps_variance = max(gps.vertical_accuracy_m ** 2, 0.01)
    baro_variance = max(barometer.variance_m2, 0.01)
    gps_local_altitude = gps.altitude_msl_m - self.home_altitude_m
    return (
        gps_local_altitude / gps_variance + barometer.altitude_m / baro_variance
    ) / (1.0 / gps_variance + 1.0 / baro_variance)
```

در `px4_normalizer.py`، `baro_alt_meter` به‌طور مستقیم از PX4 خوانده می‌شود که **ارتفاع MSL** است (در همان مقیاس `gps.altitude_msl_m`). در این‌جا `gps_local_altitude` از قبل `home_altitude_m` را کم می‌کند ولی `barometer.altitude_m` به صورت MSL خام وارد میانگین‌گیری وزنی می‌شود. نتیجه این است که وقتی فشارسنج در دسترس است، آلتیتود محلی با بایاس حدود `home_altitude_m` (معمولاً ۱۲۰۰ متر در نمونه‌ها) مخدوش می‌شود!

**پیشنهاد**:
```python
baro_local_altitude = barometer.altitude_m - self.home_altitude_m
return (gps_local_altitude/gps_variance + baro_local_altitude/baro_variance) / (...)
```

این باگ باعث می‌شود مسیرهای پروازی که نیاز به clearance نسبت به terrain دارند در انرژی مدل و تله‌متری بلادرنگ اشتباه محاسبه شوند و به تصمیمات نادرست LAND/RETURN منجر گردد.

---

## M2 🔴 بحرانی — HTTP API ماموریت کاملاً باز است (بدون احراز هویت، CORS، rate-limit)

**فایل**: `src/safe_autonomy/mission_api.py`

هیچ احراز هویت، هیچ `CORSMiddleware`، هیچ محدودیت نرخ درخواستی وجود ندارد. Endpointهای زیر بی‌واسطه در دسترس هستند:
- `POST /api/v1/maps/upload` (آپلود فایل تا 64MiB بدون سقف تعداد درخواست)
- `POST /api/v1/routes/plan` (محاسبات سنگین A* روی نقشه‌های بزرگ)
- `POST /api/v2/routes/revalidate`, `/api/v2/assurance/evaluate`, `/api/v1/scenarios/run`

روی شبکه باز این یعنی:
1. **DoS** با ارسال مداوم نقشه بزرگ یا درخواست پلنینگ،
2. **جعل نقشه/route** در دیتابیس،
3. **آپلود فایل دلخواه** (مسیر به tempfile محدود شده ولی پسوند و حجم فقط توسط میم‌تایپ چک می‌شود؛ GeoJSON های پیچیده که منجر به OOM در تحلیل شوند).

**پیشنهاد**: حداقل یک API key ثابت + CORS محدود + rate-limit ساده.

---

## M3 🟠 مهم — `assurance_repository.save_report` آمیخته از نظر تراکنش (تراکنش تودرتو/ناسازگار)

**فایل**: `src/safe_autonomy/assurance_repository.py`

```python
def save_report(self, report: AssuranceReport) -> None:
    self.save_readiness(report.readiness)     # تراکنش خودش
    self.save_energy(report.energy)           # تراکنش خودش
    with self.database.transaction() as connection:
        connection.execute("INSERT INTO assurance_reports ...")
```

اگر `INSERT` خراب شود (مثلاً نقض محدودیت UNIQUE)، رکوردهای `system_readiness_snapshots` و `energy_assessments` **از قبل** commit شده‌اند و هیچ FK به assurance_reports ندارند — یعنی رکوردهای یتیم در دیتابیس می‌مانند. بالعکس، اگر `save_readiness` موفق باشد و `save_energy` با خطا مواجه شود، readiness رکورد یتیم خواهد ماند.

**پیشنهاد**: تمام سه INSERT در یک تراکنش واحد.

---

## M4 🟠 مهم — Knowledge FTS5 هرگز به‌روز/حذف رکورد را همگام نمی‌کند

**فایل**: `migrations/003_telemetry_knowledge_advisory.sql` و `hybrid_rag.py`

- `knowledge_chunks_fts` با FTS5 ایجاد شده اما **هیچ تریگری برای محتوای جدول** وجود ندارد (مثل `content='knowledge_chunks'` که در FTS5 به‌صورت external content table استفاده می‌شود).
- در حال حاضر کد در زمان `add_document` دستی یک INSERT به FTS می‌زند، ولی:
  - اگر یک chunk حذف یا به‌روزرسانی شود (در کد فعلی هیچ به‌روزرسانی/حذف پیاده‌سازی نشده، ولی در production قطعاً نیاز خواهد بود)، FTS از جدا می‌افتد.
  - مهم‌تر از آن، چون `fts5` به صورت content-less تعریف شده و نه `content=knowledge_chunks`، rowid ها به جدول اصلی بایند نیستند و اگر chunk به‌روزشود FTS نتایج stale برمی‌گرداند.

---

## M5 🟠 مهم — Migration 002: `ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT '{}'` بر روی SQLite3 قدیمی ممکن است fail کند

**فایل**: `migrations/002_video_run_configuration.sql`
```sql
ALTER TABLE video_runs ADD COLUMN configuration_json TEXT NOT NULL DEFAULT '{}';
```
اگر دیتابیس از قبل روی نسخه‌ای ایجاد شده بود که ستون را ندارد، SQLite از نسخه 3.35.0 (2021-03-12) به بالا `ADD COLUMN ... NOT NULL DEFAULT` را پشتیبانی می‌کند. Jetson/Ubuntu 20.04 با SQLite 3.31.1 این دستور را reject می‌کند (و پروژه هدفش Jetson AGX است، مطابق `config/jetson_agx_64gb.json`). مهاجرت شکست می‌خورد و کل استپل بدون دخالت دست بالا نمی‌آید.

**پیشنهاد**: مهاجرت‌های ALTER با اطمینان از نسخه SQLite یا استفاده از جدول موقت + کپی داده (تابع ۱۲مرحله‌ای معروف SQLite).

---

## M6 🟠 مهم — HealthManager وضعیت قبلی را برای optional_modules در خود نگه می‌دارد اما status.upper() روی مقدارهای `DEGRADED/FAILED` نیز عبور می‌کند

**فایل**: `src/safe_autonomy/health_manager.py`
```python
elif heartbeat.status.upper() not in {"HEALTHY", "OK", "READY"}:
    status = GateStatus.FAIL if required else GateStatus.WARN
```
- یک ماژول که با وضعیت `DEGRADED` heartbeat بزند، به عنوان FAIL برای required_modules و WARN برای optional ثبت می‌شود.
- مشکل اصلی: **هیچ پیام `STOPPED` / `FAILED` منجر به fail-closed دائمی نمی‌شود** — یک ماژول crashed که دیگر heartbeat نمی‌فرستد بعد از `maximum_heartbeat_age_ms=1500ms` به عنوان stale/FAIL تشخیص داده می‌شود، که درست است، ولی اگر ماژول با همان فشردگی قبلی اما با `status=FAILED` به ارسال ادامه دهد، سیستم به صورت دائمی FAIL خواهد بود که درست است.
- اما: `_heartbeats` هرگز GC نمی‌شود (نشت حافظه کوچک).

---

## M7 🟡 متوسط — Px4MessageNormalizer._header با `self._sequence[kind] += 1` از صفر شروع می‌شود و هر بار که پایتون ری‌استارت sequence_no ریست می‌شود

این برای `SequenceTracker` درون-پروسه‌ای مشکلی ایجاد نمی‌کند، ولی `save_sample` در TelemetryRepository با `INSERT OR IGNORE` از header.sample_id UUID استفاده می‌کند پس داده تکراری ذخیره نمی‌شود. اما `TemporalGuard.observe` پس از ری‌استارت، `sequence_no` های reset شده را به‌عنوان `OUT_OF_ORDER_SEQUENCE` REJECT می‌کند (چون آخرین sequence پایدارشده در دیتابیس اعداد بزرگ‌تر دارد). این می‌تواند در failover باعث reject شدن تمام نمونه‌ها تا رد شدن از شماره قبلی شود.

---

## M8 🟡 متوسط — MapUploadService._simple_yaml هر رشته YAML را به درستی parse نمی‌کند

**فایل**: `src/safe_autonomy/map_ingestion.py`
تابع `_simple_yaml` یک پیاده‌سازی دستی و بسیار ساده YAML است:
- آرایه‌های تو در تو (nested lists) یا آبجکت‌های تو در تو را نمی‌پذیرد،
- رشته‌هایی که شامل کاما یا نقل‌قول هستند ممکن است اشتباه parse شوند،
- رشته‌هایی که با عدد شروع شده ولی در واقع string هستند، به اشتباه int/float می‌شوند.
- از `json.loads` فقط برای `[ ... ]` استفاده می‌شود، ولی PGم/YAML استاندارد ROS map_server معمولاً شامل:
  ```yaml
  origin: [0.0, 0.0, 0.0]
  negate: 0
  occupied_thresh: 0.65
  free_thresh: 0.196
  image: map.pgm
  mode: trinary
  ```
  که کار می‌کند، ولی هر فایل yaml پیچیده‌تر یا با فاصله‌های اضافه crash می‌کند.

---

## M9 🟡 متوسط — `scenario_engine.run_all` از `time.time_ns()` بدون respect به now_ms استفاده می‌کند (ممکن است آیتم‌های تعریف‌شده با now_ms در آینده ریجکت شوند)

**فایل**: `src/safe_autonomy/scenario_engine.py`
وقتی `now_ms` به `run_all` پاس می‌شود، `base = now_ms` و هر سناریو `base + index*10` را می‌گیرد. اما `save_scenario_result` زمان‌بندی را از assessment برمی‌گرداند که `created_at_ms = started+1` است. مشکل واقعی این است که **scenario_engine.load** در هر فراخوانی `create_app` فایل را از دیسک می‌خواند (هاردکد `config/flight_scenarios.json`) که در حالت `uvicorn --reload` در هر ریکوئست خوانده می‌شود.

---

## M10 🟡 متوسط — `_fused_altitude` کوواریانس فشارسنج را اشتباه تفسیر می‌کند

`barometer.variance_m2` در `px4_normalizer.baro` روی مقدار ثابت `1.0` تنظیم شده (چون px4 مستقیماً واریانس فشارسنج را نمی‌دهد)؛ در واقع باید برحسب متر مربع باشد. عدد `1.0` به عنوان واریانس 1 متر مربع (انحراف معیار 1 متر) قابل قبول است، اما مقدار ثابت باعث می‌شود GPS با eph/epv بهتر (مثلاً 0.5m) عملاً نادیده گرفته شود. این یک تصمیم طراحی است اما در config قابل تنظیم نیست.

---

## M11 🟡 متوسط — `mission_api.create_app` دیتابیس و تمام سرویس‌ها را به‌صورت global state می‌سازد (thread-safe نیست)

SQLite با `check_same_thread=False` و `RLock` در `Database` محافظت می‌شود، اما:
- `TemporalGuard`, `SystemHealthManager`, `LatencyRegistry`, `RouteRevalidator` همگی state درون حافظه دارند و برای همه‌ی درخواست‌ها share می‌شوند — این در `workers=1` (پیش‌فرض uvicorn با FastAPI از طریق یک thread) درست کار می‌کند اما با چند worker یا async thread pool وضعیتشان از بین می‌رود.
- `RouteRevalidator._last_replan_ms` instance variable است؛ اگر همزمان دو درخواست برسد، cooldown می‌تواند توسط هر دو شکسته شود (race condition کوچک).

---

## M12 🟡 متوسط — GeoTIFF ingestion به طور نادرست occupancy را از باند ارتفاع می‌سازد

**فایل**: `map_ingestion.py::MapUploadService._geotiff`
```python
band = dataset.read(1, masked=True)
flipped = band[::-1, :]
occupancy = bytearray(width * height)
elevation: list[float] = []
for index, value in enumerate(flipped.flatten()):
    if getattr(value, "mask", False):
        occupancy[index] = 2   # unknown
        elevation.append(0.0)
    else:
        elevation.append(float(value))
```
برای سلول‌های غیرماسک‌شده، occupancy به طور پیش‌فرض 0 (آزاد) باقی می‌ماند — صرف‌نظر از مقدار ارتفاع. انتظار می‌رفت که ناحیه‌های بسیار پرارتفاع/خالی یا ابری به‌عنوان obstacle علامت‌گذاری شوند، یا اینکه به صراحت documented شده باشد که GeoTIFF فقط لایه elevation را می‌آورد و obstacle ندارد. با این حال risk برای این سلول‌ها `0.5` می‌شود (در کد بعدی: `0.5 if value == 2 else 0.0`) — ولی risk برای سلول‌های آزاد صفر و occupancy صفر، که با منطق map سازگار است اما می‌تواند گمراه‌کننده باشد.

---

## M13 🟢 کوچک — `hybrid_rag.KnowledgeStore.add_document` و `add_edge` در صورت خطا در میانه کار، تزریق ناقص انجام می‌دهند

`add_document` یک transaction دارد اما `add_node` خارج از آن کال می‌شود: در صورت شکست `INSERT` برای knowledge_chunks_fts، knowledge_documents insert شده rollback می‌شود ولی chunk های FTS در صورت بروز خطای بخشی می‌توانند باقی بمانند (FTS5 به صورت ضمنی در همان تراکنش است در SQLite، پس مشکل واقعی نیست). `add_edge` در حالی که اعتبارسنجی `evidence_chunk_id` با REFERENCES knowledge_chunks دارد (FK)، در صورت ارجاع به chunk که وجود دارد، از ایجاد edge به لبه بدون نود ممانعت می‌کند (فقط source/target node باید از قبل موجود باشند، چک نمی‌شود).

---

## M14 🟢 کوچک — Typo در GStreamer validator و چند مورد کوچک دیگر

- `gstreamer_io.py` از `Gst.FlowReturn.NOT_NEGOTIATED` استفاده می‌کند که ثابت درست است (`NOT_NEGOTIATED` صحیح است).
- `sensor_contracts.PerceptionObject.__post_init__` چک می‌کند `depth_m > 0` اما مقداردهی صفر را رد می‌کند؛ عمق صفر معتبر نیست این درست است ولی در فیکسچرهای با عمق صفر شکست می‌خورد.
- `wiring.py` در جستجوی reachable، source_id و target_id در adjacency را به‌صورت مستقیم در modules بررسی می‌کند، اما direction edges را بر اساس source_port/target_port می‌سازد (برای تشخیص مسیر advisory به actuator درست عمل می‌کند).
- `px4_normalizer.imu` مقدار `temperature_c` را پر می‌کند ولی در `ImuSample` فیلد temperature به صورت `temperature_c: float | None = None` تعریف شده، در حالی که imu() مقدار را به تابع نمی‌فرستد (همیشه None) — خب بی‌ضرر.
- `mission_route_planner.py` در `_MOVES`، از حرکت قطری با چک‌کردن سلول‌های همسایه در برابر blocked، corner-cutting را درست منع می‌کند ✔.

---

# مشکلات مشترک

## X1. وابستگی به httpx در mission-api extra ذکر نشده

`pyproject.toml` در بخش `mission-api` شامل `fastapi` و `uvicorn` است، اما `httpx` لازم است برای starlette.testclient. در real deployment این مشکل‌ساز نیست (چرا که TestClient استفاده نمی‌شود)، ولی در تست به صورت نصب‌نشده خطا می‌دهد (که در طول بررسی مجبور شدیم دستی نصب کنیم).

## X2. Build لیب `build/lib/safe_autonomy/*` داخل بسته اصلی release زیپ شده

شاخه `build/lib/...` داخل زیپ MVP موجود است که فایل‌های کامپایل/بایلد قدیمی را شامل می‌شود. این فایل‌ها هیچ‌جا import نمی‌شوند (چون `src/` در مسیر است) ولی در هر بسته باید از طریق `sdist` یا MANIFEST.in مستثنی شوند. این به معنی آلودگی بسته است.

## X3. `artifacts/*.sqlite3` و `dist/` داخل زیپ dashboard گنجانده شده‌اند

- زیپ داشبورد شامل `frontend/dist/` است که فایل‌های build شده است (این در real deploy خوب است ولی برای CI/CD تمیز نیست).
- زیپ MVP شامل `artifacts/mission_dev_v0.6_release.sqlite3` (داده نمونه) است که هر بار که ابزارهای توسعه اجرا می‌شوند محتوایش تغییر می‌کند و binary است — شایسته است در .gitignore باشد.

## X4. هر دو پروژه فاقد CSP/CSRF/XSS protection روی HTTP endpoint ها هستند

- FastAPI ها فاقد هرگونه CSRF protection هستند (اگر cookie برای احراز هویت استفاده شود، ضروری است).
- نداشتن `Content-Security-Policy` و `X-Content-Type-Options` در nginx / FastAPI.

---

# اولویت اصلاح

## فوری (باید قبل از پرواز نصب شوند)
1. **M1** باگ ادغام ارتفاع فشارسنج (باعث خطای ارتفاع محلی)
2. **D1** احراز هویت درگاه ingest UDP/TCP
3. **D5 / M3** تراکنش‌های اتمیک برای عملیات‌های کنترلی/ assurance reports
4. **D3** پسوردهای پیش‌فرض نباید در production قابل استفاده باشند

## مهم (قبل از انتشار به تیم عملیات)
5. **M2** احراز هویت/rate-limit روی mission API
6. **D2** اعتبارسنجی `alg` در JWT یا مهاجرت به PyJWT
7. **D4** کنترل نقش در cancel intent
8. **D7** healthcheck واقعی برای دیتابیس
9. **M5** مهاجرت SQLite سازگار با نسخه‌های قدیمی Jetson

## متوسط
10. **D6 / D12** انتقال بلیت WS به هدر/بدنه و بررسی TTL
11. **M4** همگام‌سازی FTS5 با جدول اصلی (triggers)
12. **M8** استفاده از یک parser YAML واقعی (PyYAML)
13. **D9 / D10** اجباری کردن CRC32/HMAC و بایند کردن conversation به کاربر
14. **M11** بررسی thread/workers safety در stateful components

## بهبود کیفی
15. **X2 / X3** تمیز کردن build artifacts و دیتابیس‌های نمونه از زیپ‌ها
16. **X1** درج httpx به dependency های تست
17. **D13 / M13** اصلاح جزئیات UI و جلوگیری از insert های ناقص

---

**جمع‌بندی**: پروژه‌ها در کل ساختار دفاعی عمیق خوبی دارند (fail-closed gates، توابع تعیین‌گرا، تست‌های زیاد، جداسازی advisory از کنترل واقعی)، اما بیشتر باگ‌های یافت شده در مرز ورودی‌های شبکه (احراز هویت)، در همگام‌سازی state بین منابع (بارومتر-جی‌پی‌اس، تراکنش‌ها، FTS) و در سخت‌کد بودن مقادیر توسعه در production هستند.
