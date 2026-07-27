# یادداشت انتشار v0.1.0-dev1

اولین نسخه مستقل داشبورد عملیات پرواز شامل موارد زیر است:

- UI فارسی RTL و responsive برای نقش کارشناس و مدیر پرواز
- نماهای عملیات، مأموریت/A*، ویدیو/YOLO Tracking، کنترل، هشدار و دستیار مدل
- FastAPI با REST، WebSocket، UDP و TCP NDJSON
- SQLite WAL، JWT، PBKDF2، RBAC و audit trail
- کنترل نظارت‌شده با حالت simulation و gateway امضاشده
- fixture برای جریان ۲۰ هرتز و تزریق خطای GPS/link
- Docker Compose، reverse proxy و راهنمای استقرار Jetson
- ۷ تست خودکار و آزمون یکپارچه ۹۹ پیام شبکه‌ای

## محدودیت‌های شناخته‌شده

- عدد تأخیر سخت‌افزار Jetson هنوز در محیط AGX اندازه‌گیری نشده است.
- پخش ویدیو به URL خروجی WebRTC/HLS خارجی نیاز دارد؛ RTSP خام در مرورگر پخش نمی‌شود.
- adapter سخت‌افزار کنترل در این مخزن وجود ندارد و باید بعد از تست SITL/HIL به درگاه trusted متصل شود.
- SQLite برای یک نود عملیاتی مناسب است؛ برای HA چندنودی، PostgreSQL/TimescaleDB در نسخه Production توصیه می‌شود.
