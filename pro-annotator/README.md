# Offline Pro Annotator — Professional AI-Assisted Labeling with Tiny LLM

حرفه‌ای، کاملاً آفلاین، خودکار و هوشمند.

یک نرم‌افزار annotation حرفه‌ای، کاملاً آفلاین، با قابلیت‌های:

### قابلیت‌های اصلی
- ✅ **100% آفلاین** - بدون اینترنت، بدون کلود، تمام مدل‌ها محلی در `./models`
- ✅ **تشخیص خودکار با YOLO** - YOLOv8 / YOLOv11 ONNX، TensorRT اختیاری، CPU/GPU
- ✅ **پردازش دسته‌ای Batch** - خواندن پوشه‌ای هزاران عکس، فیلتر فقط کلاس‌های دلخواه شما
- ✅ **مدیریت کلاس حرفه‌ای** - تعریف کلاس‌ها، رنگ‌ها، فیلتر، جستجو
- ✅ **ابزارهای رسم**: BBox، Polygon، Point، Mask (SAM)
- ✅ **کمک LLM کوچک آفلاین** - وارد کردن مدل GGUF / ONNX / Transformers محلی (TinyLlama, Phi-3-mini, Qwen2-0.5B) برای تحلیل لیبل‌ها، QA، پیشنهاد اصلاحات، گزارش دیتاست
- ✅ **مدیریت دیتاست**: آمار کلاس‌ها، توزیع سایز باکس‌ها، تشخیص تکراری‌ها، باکس‌های کوچک/خارج از کادر، split train/val/test، active learning (نمونه‌های کم اطمینان)
- ✅ **ذخیره/استخراج**: YOLO (txt + dataset.yaml)، COCO JSON، Pascal VOC XML + وارد کردن همین فرمت‌ها
- ✅ **ویدئو**: استخراج فریم با FPS قابل تنظیم
- ✅ **UI حرفه‌ای**: PySide6 دارک تم، Thumbnail مرورگر، Canvas زوم/پن، لیست آبجکت، پنل کلاس، پنل LLM، پنل Batch

### ساختار پروژه
```
pro-annotator/
  configs/annotator.yaml
  models/
    yolov8n.onnx
    mobile_sam.onnx (اختیاری)
    llm/
      tinyllama-1.1b-chat.gguf  (اختیاری)
      phi-3-mini.onnx (اختیاری)
  pro_annotator/
    core/ project, annotation, history, dataset, validators
    ai/ detector, sam, llm_analyzer, batch_processor
    exporters/ yolo, coco, voc
    importers/ yolo, coco, voc
    ui/ main_window, canvas, panels, dialogs, styles
    utils/ colors, geometry
  scripts/download_models.py, download_llm.py
  tests/
```

### نصب سریع (Ubuntu 22.04+, Windows 10/11, Python 3.10+)

```bash
cd pro-annotator
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -e .

# دانلود مدل‌ها یکبار آنلاین (بعد کاملاً آفلاین)
python scripts/download_models.py --yolo yolov8n --sam
python scripts/download_llm.py --model tinyllama

# اجرا GUI
python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx --offline

# اجرا Batch + فقط کلاس‌های دلخواه + LLM
python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx \
  --batch-folder /path/to/images --wanted-classes person,car --conf 0.35 \
  --llm-model models/llm/tinyllama-1.1b-chat.gguf --llm-backend llama_cpp \
  --headless --export-format yolo --export-path datasets/my_dataset/export
```

### پنل LLM - چه کار می‌کند؟

مدل کوچک LLM محلی (0.5B تا 1.1B) را وارد کنید:

- **تحلیل کیفیت یک عکس**: "این عکس 2 باکس person دارد که IoU 0.95 با هم دارند - احتمال تکراری"، "باکس کوچک‌تر از 8 پیکسل"، "باکس خارج از کادر"
- **تحلیل دیتاست**: توزیع کلاس‌ها، میانگین سایز، کلاس‌های کم‌نمونه، پیشنهاد نگاشت کلاس‌ها، گزارش JSON
- **پرسش طبیعی**: "عکس‌هایی که بیش از 3 ماشین دارند را نشان بده"، "کدام عکس‌ها person بدون car دارند؟"
- **مدیریت**: پیشنهاد rename کلاس، merge کلاس‌های مشابه، حذف تکراری‌ها

Backend های پشتیبانی:
- `llama_cpp` : GGUF (بهترین برای CPU آفلاین) - `llama-cpp-python`
- `transformers` : HuggingFace محلی (TinyLlama, Phi) - `transformers`, `accelerate`
- `onnx` : ONNX Runtime LLM - `optimum`, `onnxruntime`
- `dummy` : همیشه موجود - قوانین heuristic بدون LLM، برای زمانی که مدل ندارید

همه آفلاین، بدون تماس اینترنتی در زمان اجرا.

### کلاس‌های دلخواه Batch

در UI تب Batch یا CLI:

```bash
--wanted-classes person,car,dog   # فقط این‌ها را لیبل بزن، بقیه نادیده
--batch-folder ./my_images --recursive --conf 0.4
```

فقط کلاس‌های مورد نظر شما لیبل می‌خورند، هزاران عکس در پس‌زمینه پردازش می‌شود، UI فریز نمی‌شود.

### امنیت آفلاین

- مدل‌ها در `./models` کش
- `--offline` flag جلوگیری از هر دانلود
- بدون تله‌متری، بدون کلود

### لایسنس MIT
