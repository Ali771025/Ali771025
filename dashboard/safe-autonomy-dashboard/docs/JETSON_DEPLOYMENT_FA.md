# استقرار روی Jetson AGX Orin 64GB

## پیش‌نیاز

- JetPack سازگار با Ubuntu 22.04، Docker و Compose v2
- همگامی زمان با Chrony یا PTP
- شبکه عملیات جدا از اینترنت عمومی
- خروجی WebRTC یا HLS از GStreamer برای مرورگر؛ RTSP مستقیماً در مرورگر پخش نمی‌شود

## اجرا

```bash
cp .env.example .env
# همه گذرواژه‌ها و JWT secret را تغییر دهید
docker compose -f deploy/docker-compose.yml up --build -d
```

داشبورد روی `http://JETSON_IP:8088` است. ورودی‌ها: UDP `15010` و TCP `15011`. برای تست:

```bash
python3 tools/fixture_sender.py --host 127.0.0.1 --hz 20 --fault-after 20
```

## ویدیو

GStreamer را به سرویس WebRTC/HLS جداگانه متصل و هنگام build مقدار `VITE_VIDEO_STREAM_URL` را تنظیم کنید. Detectionها مستقل از تصویر، از topic `vision` می‌آیند و overlay مرورگر با مختصات نرمال‌شده ترسیم می‌شود. برای تأخیر کمتر از HLS معمولی، WebRTC پیشنهاد می‌شود.

## چک تولید

1. `DASH_ENV=production` و JWT secret تصادفی حداقل ۳۲ کاراکتر.
2. تعویض هر دو گذرواژه اولیه پیش از ساخت دیتابیس.
3. TLS در reverse proxy و محدودسازی CORS به دامنه واقعی.
4. `DASH_CONTROL_MODE=disabled` تا پایان تست‌های SITL/HIL و بازبینی ایمنی.
5. فعال‌سازی `gateway` فقط با URL داخلی HTTPS و secret مجزا.
6. آزمون قطع GPS، افت لینک، باتری کم، stale telemetry و از دست رفتن تأیید مدیر.
7. ثبت latency p50/p95/p99 روی خود AGX؛ اعداد محیط توسعه معیار سخت‌افزار نیستند.

