# هسته پژوهشی خودگردان ایمن - نسخه 0.6.0-dev1

این پروژه نسخه Developer معماری سند «معماری هوشمند، مستندپذیر و ایمن برای سامانه خودگردان پژوهشی» است. دامنه آن شبیه سازی نرم افزاری، دریافت فقط خواندنی تله متری PX4/ROS 2، پردازش YOLO، Hybrid RAG، Knowledge Graph و Transformer advisory برای کاربردهای غیرتسلیحاتی است. هیچ فرمان موتور، عملگر، waypoint یا setpoint پروازی از لایه هوش مصنوعی منتشر نمی شود.

## آنچه در نسخه Developer کار می کند

- قراردادهای داده نسخه دار و سخت گیرانه برای وضعیت، مانع، مسیر و رأی ایمنی
- World Model با timestamp اجباری برای pose/obstacle/battery، freshness، quality و uncertainty
- برنامه ریز قطعی A* روی شبکه دوبعدی با inflation مانع
- Safety Supervisor مستقل با گیت های تازگی، محدوده، دینامیک، برخورد، انرژی و مالکیت کنترل
- Mission Manager با حالت های محدود و قابل آزمون
- Audit Log از نوع JSONL با correlation ID
- دیتابیس SQLite نسخه دار با migration و foreign key
- ذخیره video run، metadata، detection، World Model، obstacle، trajectory، safety gate و audit
- probe و نمونه برداری ویدیو با FFmpeg/FFprobe
- آداپتر واقعی Ultralytics YOLO با model path محلی و allowlist کلاس
- قراردادهای GPS، IMU، Barometer، Magnetometer، Airspeed، Rangefinder و Battery
- bridge فقط خواندنی ROS 2/PX4 و کنترل timestamp، sequence، quality و calibration
- هم زمان ساز تله متری با freshness، skew و fusion ارتفاع GPS/Barometer
- تصمیم گیر قطعی محدود برای `CONTINUE/HOLD/RETURN/LAND/REQUEST_REROUTE`
- RAG هیبریدی Dense + FTS5/BM25 + Graph traversal با Reciprocal Rank Fusion
- آداپتر Qwen3 Embedding و Qwen3 Reranker مبتنی بر Transformer
- Knowledge Graph دارای node/edge، وضعیت تأیید و provenance تا chunk سند
- آداپتر Ollama برای Qwen3-4B با JSON Schema، Evidence Gate و TTL
- سناریوهای SIL برای مسیر سالم، داده کهنه، باتری کم و تعارض مالک کنترل
- تست های خودکار فقط با کتابخانه استاندارد Python
- دریافت زنده V4L2/RTSP/فایل با GStreamer appsink و صف کم تأخیر `drop-oldest`
- اجرای YOLO و ByteTrack روی فریم حافظه با ID پایدار و trail روی تصویر
- انتشار تصویر حاشیه نویسی شده با GStreamer appsrc روی RTP/UDP یا RTSP push
- همگام سازی فریم دوربین با GPS/IMU/PX4 بر اساس `host_monotonic_ms`
- ثبت camera stream، فریم، track، sync، latency، drop و سلامت ماژول در SQLite
- سیم کشی ماشین خوان کل سامانه با port/contract نسخه دار و validator ایمنی
- ورود و تحلیل نقشه‌های `GeoJSON`، شبکه اشغال `PGM/ROS` و `GeoTIFF` اختیاری
- rasterization محدوده پرواز، مانع، restricted zone، risk layer و landing zone
- A* قطعی چندمعیاره و 2.5D با inflation، ریسک، ارتفاع زمین، نرخ صعود/نزول و مسیرهای جایگزین
- تحلیل فاز و وضعیت پرواز از preflight تا landing/emergency با transition validation
- کاتالوگ ۲۷ سناریوی SIL شامل ناوبری، انرژی، ارتباط، geofence، مسیر، ادراک و دینامیک
- API توسعه‌ای برای آپلود نقشه، برنامه‌ریزی مسیر، تحلیل وضعیت و اجرای سناریو
- پروفایل منابع مخصوص Jetson AGX 64GB
- Temporal Guard نسخه ۲ برای رد داده کهنه، آینده، خارج از ترتیب، clock regression و skew بین منابع
- System Health Manager با heartbeat، dependency readiness و وضعیت‌های `READY/DEGRADED/NOT_READY`
- پیش‌بینی ریسک اشیای متحرک روی افق زمانی محدود و تولید کپی immutable از نقشه پویا
- برآورد انرژی مسیر با ظرفیت باتری، reserve، صعود، توان avionics و headwind
- Route Revalidation پیوسته با cross-track error، پیشرفت مسیر، corridor risk و cooldown ضد نوسان
- Mission Assurance چندگیتی با خروجی `PASS/WARN/FAIL` و هش محتوایی SHA-256
- رجیستری latency محدود با P50/P95/P99 و نسبت رعایت بودجه زمانی
- API نسخه ۲ و migration ششم برای ثبت شواهد runtime و assurance

## مرز ایمنی

```text
GPS/IMU/.../YOLO -> Synchronizer -> Telemetry/World Model -> Deterministic Policy/Planner
                                              |                         |
Documents -> Dense + Lexical + Knowledge Graph + Reranker              |
                                              |                         v
                                              +-> Transformer -> Evidence Gate
                                                       typed intent only
```

خروجی YOLO فقط `Detection2D` است و بدون depth/calibration/tracking/TTC به obstacle متریک یا تغییر مسیر تبدیل نمی شود. Transformer فقط پیشنهاد محدود می دهد؛ Planner عددی و Safety Supervisor مستقل باقی می مانند.

## اجرای سریع

از ریشه پروژه:

```bash
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m safe_autonomy.simulator --scenario nominal
PYTHONPATH=src python3 -m safe_autonomy.simulator --scenario stale_state
PYTHONPATH=src python3 -m safe_autonomy.ai_demo --scenario incomplete_depth
PYTHONPATH=src python3 -m safe_autonomy.ai_demo --scenario bounded_ttc
PYTHONPATH=src python3 -m safe_autonomy.wiring --config config/system.wiring.json
PYTHONPATH=src python3 -m safe_autonomy.mission_analysis \
  --database artifacts/mission_dev_v0.6.sqlite3 demo
```

## تحلیل نقشه و مسیر جایگزین

ورود نقشه نمونه:

```bash
PYTHONPATH=src python3 -m safe_autonomy.mission_analysis \
  --database artifacts/mission_dev_v0.6.sqlite3 \
  ingest-map --map maps/sample_mission.geojson
```

خروجی شامل `map_id` و تحلیل تعداد سلول آزاد/اشغال/ناشناخته، تراکم مانع، پیوستگی فضای آزاد و هشدارهای نقشه است. سپس با `map_id` خروجی:

```bash
PYTHONPATH=src python3 -m safe_autonomy.mission_analysis \
  --database artifacts/mission_dev_v0.6.sqlite3 \
  plan-route \
  --map-id MAP_ID \
  --start-x 10 --start-y 10 \
  --goal-x 180 --goal-y 125 \
  --start-altitude 25 --cruise-altitude 60 \
  --inflation 2 --clearance 20 --alternatives 3
```

مسیر اول کم‌هزینه‌ترین نتیجه معتبر A* است. مسیرهای بعدی با جریمه مسیرهای قبلی تولید می‌شوند و باید حداقل distinctness تعیین‌شده را داشته باشند. هیچ مختصات یا waypoint از LLM دریافت نمی‌شود.

## اجرای سناریوهای مهم پرواز

```bash
PYTHONPATH=src python3 -m safe_autonomy.mission_analysis \
  --database artifacts/mission_dev_v0.6.sqlite3 \
  run-scenarios --config config/flight_scenarios.json
```

کاتالوگ اولیه ۲۷ سناریو دارد: حالت‌های عادی preflight/takeoff/climb/cruise/approach/landing و خطاهای GPS، estimator، telemetry، باتری، لینک، geofence، انحراف مسیر، TTC، terrain clearance، tilt، سرعت، descent، takeoff بدون climb، landing zone، camera، tracker، map age و transition نامعتبر.

## API آپلود نقشه و تحلیل مأموریت

```bash
pip install -e '.[mission-api]'
safe-autonomy-mission-api \
  --database artifacts/mission_dev_v0.6.sqlite3 \
  --host 0.0.0.0 --port 8088
```

Endpointهای توسعه‌ای:

- `POST /api/v1/maps/upload`
- `POST /api/v1/routes/plan`
- `POST /api/v1/flight/analyze`
- `POST /api/v1/scenarios/run`
- `GET /health`

Endpointهای تخصصی نسخه ۲:

- `POST /api/v2/time/observe` برای sequence/freshness/skew gate
- `POST /api/v2/health/heartbeat` و `GET /api/v2/health/readiness`
- `POST /api/v2/routes/energy` برای انرژی و reserve
- `POST /api/v2/routes/revalidate` برای مسیر پویا و trackهای متحرک
- `POST /api/v2/assurance/evaluate` برای گزارش نهایی تضمین مأموریت
- `GET /api/v2/metrics/latency/{metric_name}` برای P50/P95/P99

این endpointها فقط تحلیل، گزارش و پیشنهاد محدود تولید می‌کنند. فیلدهای command، setpoint، actuator و waypoint-command در آداپتر API رد می‌شوند.

برای GeoTIFF نصب `pip install -e '.[maps]'` لازم است. GeoTIFF جغرافیایی باید پیش از برنامه‌ریزی به CRS متریک محلی reproject شود.

## نصب ماژول GStreamer و ردیابی

روی Ubuntu 22.04 ابتدا runtime و pluginها را نصب کنید:

```bash
sudo apt update
sudo apt install -y \
  gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
  gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 \
  libgirepository1.0-dev libcairo2-dev pkg-config python3-dev

python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e '.[perception,gstreamer]'
```

روی Jetson وجود pluginهای سخت افزاری را قبل از اجرا کنترل کنید:

```bash
gst-inspect-1.0 nvvidconv
gst-inspect-1.0 nvv4l2decoder
gst-inspect-1.0 nvv4l2h264enc
```

وزن YOLO باید از قبل روی دیسک باشد؛ runtime دانلود خودکار انجام نمی دهد.

## اجرای دوربین Magewell یا UVC با YOLO + ByteTrack

Magewell Mini SDI روی `/dev/video0` و خروجی H.264 سخت افزاری Jetson:

```bash
safe-autonomy-realtime-vision \
  --profile magewell_sdi_1080p25 \
  --device /dev/video0 \
  --model /opt/models/yolo11n.pt \
  --output rtp_udp_jetson \
  --publish-host 192.168.1.20 \
  --publish-port 5600
```

دوربین UVC شما روی `/dev/video1` با YUYV، وضوح 1080p و 10 fps:

```bash
safe-autonomy-realtime-vision \
  --profile usb_uvc_1080p10 \
  --device /dev/video1 \
  --model /opt/models/yolo11n.pt \
  --output rtp_udp_x86 \
  --publish-host 127.0.0.1 \
  --publish-port 5600
```

دریافت RTP/H.264 روی رایانه مقصد:

```bash
gst-launch-1.0 -v \
  udpsrc port=5600 caps="application/x-rtp,media=video,encoding-name=H264,payload=96" \
  ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink sync=false
```

برای RTSP ورودی از `rtsp_h264_x86` یا `rtsp_h264_jetson` و گزینه `--uri` استفاده کنید. خروجی `rtsp_push_x86` نیازمند RTSP server موجود و گزینه `--publish-uri` است.

## منطق همگام سازی

ROS 2/PX4 هنگام ساخت `TelemetryFrame` زمان monotonic میزبان را ثبت می کند. فریم دوربین نیز در callback مربوط به appsink همان clock را می گیرد. `MultimodalSynchronizer` نزدیک ترین فریم تله متری را انتخاب می کند:

- skew تا 50 ms: `MATCHED`
- telemetry موجود ولی خارج حد: `TOO_OLD`
- نبود telemetry دارای monotonic clock: `MISSING`

هیچ حالت قدیمی یا مفقود به صورت ساختگی match نمی شود. اگر دوربین و PX4 روی دو کامپیوتر جدا باشند، برای Production باید PTP/PPS یا offset اندازه گیری شده اضافه شود.

## اعتبارسنجی سیم کشی کل سامانه

```bash
PYTHONPATH=src python3 -m safe_autonomy.wiring \
  --config config/system.wiring.json
```

validator موارد زیر را کنترل می کند: وجود ماژول های اجباری، portهای معتبر، قرارداد دقیق دو سر اتصال، producer یکتا، سیاست صف معتبر، قراردادهای ممنوع PX4 و نبود هر مسیر Transformer/RAG به flight-control یا actuator. نمای انسانی مسیرها در `docs/system-wiring.md` است.

خروجی رخدادها در `artifacts/audit.jsonl` و دیتابیس `artifacts/autonomy_dev.sqlite3` ثبت می شود.

## اجرای ویدیوی ارسالی در حالت metadata

این فرمان بدون نیاز به پکیج YOLO، مشخصات و checksum ویدیو را در دیتابیس ثبت می کند:

```bash
PYTHONPATH=src python3 -m safe_autonomy.video_pipeline \
  --video /path/to/input.mp4 \
  --database artifacts/autonomy_dev.sqlite3 \
  --backend metadata
```

## اجرای YOLO واقعی

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[perception]'

safe-autonomy-video \
  --video /path/to/input.mp4 \
  --database artifacts/autonomy_dev.sqlite3 \
  --backend ultralytics \
  --model /path/to/yolo11n.pt \
  --classes airplane \
  --sample-fps 5 \
  --confidence 0.30
```

وزن مدل باید محلی، مشخص و checksum شده باشد. دانلود خودکار وزن در مسیر Production مجاز نیست.

## اجرای GPS/IMU/YOLO + Hybrid RAG + Knowledge Graph

نسخه بدون مدل خارجی و کاملاً قابل تست:

```bash
PYTHONPATH=src python3 -m safe_autonomy.ai_demo \
  --database artifacts/ai_dev_v0.3.sqlite3 \
  --scenario incomplete_depth
```

سناریوهای موجود: `nominal`، `incomplete_depth`، `bounded_ttc`، `stale` و `low_battery`.

برای استفاده از Transformerهای بازیابی:

```bash
pip install -e '.[rag]'
```

مدل پیشنهادی embedding برابر `Qwen/Qwen3-Embedding-0.6B` و reranker برابر `Qwen/Qwen3-Reranker-0.6B` است. کلاس های `SentenceTransformerEmbedder` و `QwenCrossEncoderReranker` در کد آماده اند. fallback تست آفلاین Hashing/TokenOverlap است و جای مدل Production را نمی گیرد.

برای LLM مشورتی محلی:

```bash
PYTHONPATH=src python3 -m safe_autonomy.ai_demo \
  --database artifacts/ai_dev_v0.3.sqlite3 \
  --scenario bounded_ttc \
  --ollama
```

Ollama باید مدل تنظیم شده در `config/ai.dev.json` را در اختیار داشته باشد. پاسخ مدل با schema بسته، evidence ID، TTL و human-confirmation کنترل می شود.

برای ساخت نام مدل از GGUF محلی:

```bash
ollama create safe-advisory-qwen3-4b -f deploy/Modelfile.qwen3-4b
```

## Bridge فقط خواندنی ROS 2/PX4

پس از source کردن ROS 2 Humble و workspace سازگار `px4_msgs`:

```bash
PYTHONPATH=src python3 -m safe_autonomy.ros2_bridge \
  --database artifacts/telemetry_dev.sqlite3 \
  --home-lat 35.7000 \
  --home-lon 51.3000 \
  --home-alt 1200
```

فهرست topicها و topicهای صریحاً ممنوع برای publication در `config/topics.ros2.yaml` ثبت شده است.

## مشاهده امن دیتابیس

```bash
PYTHONPATH=src python3 -m safe_autonomy.db_cli \
  --database artifacts/autonomy_dev.sqlite3
```

این ابزار دیتابیس را در حالت read-only باز می کند و integrity، migrationها، تعداد رکوردها و آخرین اجرای ویدیو را نمایش می دهد.

## جداول دیتابیس

| گروه | جدول ها |
| --- | --- |
| ویدیو و ادراک | `video_runs`, `detections` |
| مدل جهان | `world_snapshots`, `world_obstacles` |
| برنامه ریزی | `trajectories`, `trajectory_points` |
| ایمنی | `safety_decisions`, `safety_gate_results` |
| حسابرسی | `audit_events`, `schema_migrations` |
| تله متری | `telemetry_samples`, `telemetry_frames`, `telemetry_perception_objects` |
| RAG | `knowledge_documents`, `knowledge_chunks`, `rag_queries`, `rag_evidence` |
| گراف دانش | `knowledge_nodes`, `knowledge_edges` |
| Transformer advisory | `advisory_proposals` |
| دوربین و track زنده | `camera_streams`, `vision_frames`, `vision_objects` |
| همگام سازی | `sensor_vision_sync` |
| سلامت و سیم کشی | `module_health_events`, `wiring_revisions` |
| نقشه مأموریت | `mission_maps` |
| درخواست و مسیر جایگزین | `route_plan_requests`, `route_candidates`, `route_points` |
| تحلیل حالت پرواز | `flight_assessments`, `flight_findings` |
| سناریوهای SIL | `scenario_definitions`, `scenario_runs`, `scenario_events` |
| زمان و ترتیب داده | `temporal_observations` |
| آمادگی سامانه | `system_readiness_snapshots` |
| انرژی و مسیر پویا | `energy_assessments`, `route_revalidations` |
| تضمین و SLO | `assurance_reports`, `latency_slo_snapshots` |

## ساختار پروژه

```text
src/safe_autonomy/contracts.py   قراردادهای داده و enumها
src/safe_autonomy/world_model.py مدل جهان و کنترل تازگی داده
src/safe_autonomy/planner.py     برنامه ریز قطعی A*
src/safe_autonomy/safety.py      گیت های مستقل ایمنی
src/safe_autonomy/mission.py     ماشین حالت و orchestration
src/safe_autonomy/audit.py       ثبت رخداد قابل بازپخش
src/safe_autonomy/database.py    migration و repository دیتابیس
src/safe_autonomy/perception.py  probe ویدیو و adapter مدل YOLO
src/safe_autonomy/video_pipeline.py pipeline ویدیو تا دیتابیس
src/safe_autonomy/db_cli.py       بازرسی read-only دیتابیس
src/safe_autonomy/sensor_contracts.py قرارداد تمام حسگرها
src/safe_autonomy/sensor_fusion.py هم زمان سازی و fusion توسعه ای
src/safe_autonomy/px4_normalizer.py تبدیل px4_msgs به قرارداد داخلی
src/safe_autonomy/ros2_bridge.py  subscriber فقط خواندنی ROS 2/PX4
src/safe_autonomy/hybrid_rag.py   Dense/BM25/Graph/RRF/Reranker
src/safe_autonomy/advisory.py     Qwen/Ollama، JSON Schema و Evidence Gate
src/safe_autonomy/coordinator.py  اتصال تصمیم قطعی، RAG/KG و Transformer
src/safe_autonomy/ai_demo.py      سناریوی یکپارچه قابل اجرا
src/safe_autonomy/gstreamer_io.py appsink/appsrc و صف کم تأخیر
src/safe_autonomy/tracking.py     YOLO + ByteTrack و overlay/trail
src/safe_autonomy/realtime_vision.py حلقه زنده تصویر تا stream و دیتابیس
src/safe_autonomy/multimodal_sync.py تطبیق monotonic دوربین و تله متری
src/safe_autonomy/vision_repository.py ذخیره فریم/track/sync/health
src/safe_autonomy/wiring.py       validator سیم کشی و قراردادها
src/safe_autonomy/map_ingestion.py ورود و تحلیل GeoJSON/PGM/GeoTIFF
src/safe_autonomy/mission_route_planner.py برنامه‌ریز A* چندمعیاره 2.5D
src/safe_autonomy/flight_state_analyzer.py تحلیل فاز، سلامت و پیشنهاد محدود
src/safe_autonomy/scenario_engine.py fault injection و ارزیابی سناریو
src/safe_autonomy/mission_repository.py ذخیره نقشه/مسیر/وضعیت/سناریو
src/safe_autonomy/mission_analysis.py CLI یکپارچه توسعه‌ای
src/safe_autonomy/mission_api.py API آپلود و تحلیل مأموریت
src/safe_autonomy/temporal_guard.py گیت زمان، freshness، sequence و skew
src/safe_autonomy/health_manager.py heartbeat و readiness وابستگی‌ها
src/safe_autonomy/dynamic_risk.py پیش‌بینی track و نقشه ریسک پویا
src/safe_autonomy/route_revalidation.py پایش corridor و درخواست replan محدود
src/safe_autonomy/energy_model.py تخمین انرژی، reserve و باد
src/safe_autonomy/observability.py شاخص‌های P50/P95/P99 محدود
src/safe_autonomy/mission_assurance.py گزارش نهایی PASS/WARN/FAIL
src/safe_autonomy/assurance_repository.py persistence شواهد نسخه ۲
src/safe_autonomy/assurance_demo.py دموی یکپارچه release نسخه ۰.۶
src/safe_autonomy/simulator.py   سناریوهای SIL و fault injection
config/policy.json               سیاست ایمنی قابل نسخه بندی
config/ai.dev.json               مدل ها و سیاست RAG/تصمیم
config/topics.ros2.yaml           قرارداد topic و QoS
migrations/001_initial.sql       schema اولیه دیتابیس
migrations/003_telemetry_knowledge_advisory.sql schema تله متری و دانش
migrations/004_realtime_vision_wiring.sql schema تصویر زنده و سیم کشی
migrations/005_mission_maps_routes_scenarios.sql schema نقشه، مسیر و سناریو
migrations/006_runtime_assurance_observability.sql schema زمان، سلامت، انرژی، مسیر پویا و assurance
config/camera.gstreamer.dev.json  پروفایل های Magewell/UVC/RTSP/Jetson/x86
config/system.wiring.json         منبع حقیقت اتصال همه ماژول ها
config/flight_scenarios.json      کاتالوگ سناریوهای مهم پرواز
config/jetson_agx_64gb.json       بودجه منابع و سیاست اجرای Jetson AGX
maps/sample_mission.geojson       نقشه نمونه قابل آپلود
docs/architecture.md             تصمیم های معماری و مرزهای اتصال
docs/model-selection.md          انتخاب مدل بر اساس سخت افزار
docs/production-gate.md          شروط شروع نسخه Production
docs/traceability.csv            ردیابی نیازمندی تا آزمون
```

## مسیر نسخه Production بعدی

1. جایگزینی SQLite ground service با PostgreSQL/TimescaleDB.
2. انتقال Dense/Sparse index به Qdrant و property graph به Neo4j.
3. اجرای Qwen3-Embedding/Reranker واقعی و ساخت Golden QA فارسی.
4. کالیبراسیون دوربین/depth واقعی و محاسبه TTC با covariance؛ track دوبعدی فعلی فاصله نیست.
5. ROS 2/PX4 SITL سپس HIL؛ هیچ اتصال پروازی واقعی پیش از دروازه ایمنی انجام نمی شود.

## معیار پذیرش v0.6-dev

- Planner برای ورودی یکسان دقیقاً مسیر یکسان بسازد.
- World Model داده بدون timestamp/quality را نپذیرد.
- داده کهنه، مسیر خارج geofence، سرعت بیش از حد، باتری کم یا مالک ناشناخته به PASS نرسد.
- قطع کامل لایه advisory اثری بر Planner/Safety نداشته باشد.
- همه تصمیم ها دارای request/correlation ID و gate trace باشند.
- migration چندباره بدون خرابی اجرا شود و foreign key فعال باشد.
- هر video run دارای SHA-256 ورودی، SHA-256 مدل، نسخه مدل، sample FPS، allowlist، confidence، status و خطای قابل حسابرسی باشد.
- هیچ Detection2D بدون depth به World Model فیزیکی ارتقا داده نشود.
- GPS/IMU/Battery کهنه یا ناهمگام به HOLD منجر شود.
- Proposal دارای waypoint یا evidence ناشناخته توسط parser/gate رد شود.
- Hybrid RAG هر سه کانال lexical، dense و graph را با provenance ثبت کند.
- Knowledge edge بدون evidence chunk قابل ثبت نباشد.
- قطع Ollama/Qdrant/Neo4j کنترل قطعی و Safety را از کار نیندازد.
- صف تصویر زیر بار، فریم قدیمی را حذف کند و حافظه بدون حد رشد نکند.
- track متحرک مشابه ID پایدار بگیرد و track منقضی ID جدید دریافت کند.
- sync فقط با clock مشترک و skew مجاز `MATCHED` شود.
- سیم کشی دارای contract اشتباه، PX4 command یا مسیر advisory به actuator رد شود.
- نقشه خارج محدودیت حجم، CRS نامتریک یا بدون فضای آزاد رد/Degraded شود.
- مسیر A* وارد سلول اشغال/ناشناخته یا محدوده inflation نشود.
- برای نقشه دارای گذرگاه مستقل حداقل دو مسیر متمایز قابل تولید باشد.
- terrain clearance و نرخ صعود/نزول هر مسیر مستقل اعتبارسنجی شود.
- تمام ۲۷ سناریوی اعلام‌شده نتیجه مورد انتظار قطعی داشته باشند.
- transition نامعتبر فاز پرواز به `CONTINUE` منجر نشود.
- داده stale/future/out-of-order یا clock regression توسط Temporal Guard رد شود.
- از دست رفتن heartbeat ماژول ضروری، readiness را `NOT_READY` کند.
- track کهنه وارد dynamic-risk نشود و نقشه مرجع immutable بماند.
- مانع جدید در کل corridor مسیر، نه فقط vertexها، تشخیص داده شود.
- مسیر فاقد reserve انرژی هرگز Assurance برابر `PASS` نگیرد.
- هش Assurance با ورودی محتوایی یکسان، مستقل از UUID، تکرارپذیر باشد.
- API هر فیلد command، setpoint، actuator یا waypoint-command را رد کند.
- تمام ۷۸ تست با وابستگی‌های API موفق باشند.
