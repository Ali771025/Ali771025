# قرارداد شبکه نسخه ۱.۰

هر Datagram در UDP و هر خط در TCP یک JSON مستقل با حداکثر یک مگابایت است:

```json
{
  "schema_version": "1.0",
  "message_id": "7a530ddb-34e0-4c85-bd20-c62185e43465",
  "topic": "telemetry",
  "source": "px4-bridge",
  "sequence_no": 412,
  "sent_at_ms": 1770000000123,
  "host_monotonic_ms": 882311,
  "payload": {"battery_percent": 76.2, "gps_fix": 3},
  "crc32": "6f0ec9a1"
}
```

`crc32` اختیاری است، اما در تولید توصیه می‌شود. مقدار آن از JSON بدون فیلد `crc32`، با مرتب‌سازی کلیدها و separator فشرده UTF-8 محاسبه می‌شود. CRC امنیت ایجاد نمی‌کند؛ شبکه عملیاتی باید VLAN مجزا و در صورت عبور از شبکه نامطمئن WireGuard داشته باشد.

## Topicها

| Topic | حمل پیشنهادی | Payload اصلی |
|---|---|---|
| `telemetry` | UDP | موقعیت، ارتفاع، سرعت، attitude، باتری، GPS، لینک، EKF، mode |
| `vision` | UDP | FPS، inference، trackهای نرمال‌شده `x/y/w/h` |
| `flight_assessment` | UDP | phase، risk_level، ETA |
| `route_candidates` | TCP | مسیر منتخب، لیست مسیرها و هزینه‌ها |
| `module_health` | TCP | نگاشت نام ماژول به وضعیت |
| `alert` | TCP | id، severity، code، title، detail |
| `scenario_report` | TCP | نتیجه سناریوی SIL و evidence |

TCP برای هر خط معتبر پاسخ `{"ok":true,"sequence_no":N}` و برای پیام نامعتبر پاسخ خطا می‌دهد. منتشرکننده فقط پس از ACK پیام بعدی را ارسال کند یا پنجره ارسال محدود و retry دارای backoff بسازد.

