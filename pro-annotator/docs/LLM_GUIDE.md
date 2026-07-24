# LLM Guide - تحلیل لیبل با مدل کوچک آفلاین

## چرا LLM برای Annotation؟

- QA خودکار: تشخیص باکس‌های تکراری، کوچک، خارج از کادر
- توضیح خودکار هر عکس: "این عکس 3 ماشین و 1 عابر دارد..."
- پرسش طبیعی: "عکس‌هایی که بیش از 2 سگ دارند" - فارسی و انگلیسی
- مدیریت کلاس: پیشنهاد merge (مثلاً car + truck -> vehicle) یا rename
- گزارش دیتاست: توزیع کلاس‌ها، imbalance، پیشنهاد بهبود

## مدل‌های پیشنهادی آفلاین (0.4GB تا 2.2GB)

| مدل | سایز | زبان | کیفیت | سرعت CPU |
|-----|------|------|--------|-----------|
| qwen2-0.5b Q4 | 0.4GB | فارسی+انگلیسی عالی | خوب | بسیار سریع |
| tinyllama 1.1B Q4 | 0.6GB | انگلیسی | متوسط | سریع |
| qwen2-1.5b Q4 | 1.0GB | فارسی+انگلیسی عالی | خوب-عالی | متوسط |
| phi-2 2.7B Q4 | 1.6GB | انگلیسی | عالی | کند |
| phi-3-mini 3.8B Q4 | 2.2GB | انگلیسی+ | عالی | کندتر |

**توصیه برای فارسی:** qwen2-0.5b یا qwen2-1.5b (پشتیبانی فارسی عالی)

## دانلود

```bash
python scripts/download_llm.py --model qwen2-0.5b --dest models/llm
python scripts/download_llm.py --model tinyllama --dest models/llm
python scripts/download_llm.py --list
```

یا دستی از HuggingFace دانلود کنید و در models/llm قرار دهید.

## Backend ها

### llama_cpp (GGUF) - توصیه شده برای CPU
```bash
pip install llama-cpp-python
python -m pro_annotator --project datasets/my --model models/yolov8n.onnx --llm-model models/llm/qwen2-0_5b-instruct-q4_0.gguf --llm-backend llama_cpp
```

### transformers (HF folder)
```bash
pip install transformers accelerate torch
# مدل را از HF دانلود کنید (یکبار آنلاین) سپس آفلاین استفاده کنید
python -m pro_annotator --llm-model models/llm/Qwen2-0.5B-Instruct --llm-backend transformers
```

### onnx (ONNX Runtime LLM - via optimum)
```bash
pip install optimum[onnxruntime] transformers
# تبدیل مدل به ONNX (اسکریپت optimum)
```

### dummy (بدون مدل - همیشه کار می‌کند)
اگر مدل ندارید، dummy backend قوانین heuristic را اجرا می‌کند:
- باکس تکراری IoU>0.95
- باکس کوچک <8px
- خارج از کادر
- توزیع کلاس، imbalance

```bash
python -m pro_annotator --project datasets/my --model models/yolov8n.onnx --llm-backend dummy
```

## استفاده در UI

1. Tab "LLM QA" -> Browse مدل -> Load LLM
2. Analyze Current Image: تحلیل عکس فعلی
3. Analyze Dataset: تحلیل کل دیتاست
4. Query: بنویس "images with more than 3 cars" یا فارسی "عکس‌هایی که ماشین ندارند"

## استفاده Headless (Batch + LLM)

```bash
python -m pro_annotator --project datasets/my_dataset \
  --model models/yolov8n.onnx \
  --batch-folder /data/images --wanted-classes person,car \
  --llm-model models/llm/qwen2-0_5b-instruct-q4_0.gguf --llm-backend llama_cpp \
  --headless --export-format yolo --export-path export/
```

خروجی:
- `llm_report.json`: گزارش تحلیل
- `dataset_stats.json`: آمار
- `export_yolo/`: لیبل‌ها

## پرامپت‌ها

سیستم پرامپت پیش‌فرض:
"You are a professional dataset QA assistant for object detection labeling..."

قابل تنظیم در `configs/annotator.yaml` -> `llm.system_prompt`

## آفلاین بودن

- تمام مدل‌ها محلی
- `--offline` flag جلوگیری از دانلود
- بدون اینترنت، بدون تله‌متری

## نکات حرفه‌ای

- برای هزاران عکس، ابتدا batch با wanted-classes، سپس LLM QA برای پیدا کردن خطاها
- از Query برای فیلتر کردن عکس‌های خاص استفاده کنید
- از Dataset Report برای تصمیم train/val split استفاده کنید
- اگر فارسی کار می‌کنید، Qwen2 بهترین گزینه است
```

cat > pro-annotator/docs/BATCH_GUIDE.md <<'MD'
# Batch Guide - پردازش دسته‌ای فقط کلاس‌های دلخواه

## مشکل
شما 10,000 عکس دارید و فقط می‌خواهید `person` و `car` را لیبل بزنید، بقیه کلاس‌ها نادیده.

## راه حل Pro Annotator

### GUI

1. پروژه باز کنید
2. Tab "Classes" -> چک باکس‌های Wanted Classes: فقط person, car را تیک بزنید (یا Select All سپس فقط دو تا را نگه دارید)
3. Tab "Batch" -> Browse Folder -> انتخاب پوشه با 10k عکس
4. Conf 0.35, Recursive تیک, Overwrite AI تیک
5. Start Batch
   - Progress bar: 1/10000, 2/10000 ...
   - UI فریز نمی‌شود (thread جدا)
   - هر 50 عکس autosave
   - فقط person, car لیبل می‌خورد

### CLI

```bash
python -m pro_annotator --project datasets/my \
  --model models/yolov8n.onnx \
  --batch-folder /path/to/10k_images \
  --wanted-classes person,car \
  --conf 0.35 --recursive --offline
```

### Headless + Export

```bash
python -m pro_annotator --project datasets/my \
  --model models/yolov8n.onnx \
  --batch-folder /data/images \
  --wanted-classes person,car \
  --headless --export-format yolo --export-path datasets/my/export
```

### منطق فیلتر

- `set_wanted_classes(["person","car"])` هم نام و هم ID را ساپورت می‌کند
- `detector.set_wanted_classes` -> فقط این کلاس‌ها از خروجی YOLO نگه داشته می‌شوند
- `project.is_wanted(class_id, class_name)` -> چک در همه جا
- اگر wanted خالی = ALL کلاس‌ها

### کارایی

- Threaded: capture -> inference -> save
- Bounded queue نیست چون batch فایل‌محور است، اما progress callback دارد
- برای 10k عکس ~ 640x480 با YOLOv8n CPU ~ 10 FPS -> ~ 16 دقیقه
- با GPU ~ 30-60 FPS -> ~ 3-5 دقیقه
- با `--max-images 100` برای تست سریع

### ترکیب با LLM

بعد از batch:

- Tab LLM QA -> Analyze Dataset -> گزارش می‌دهد "Class person 8000 object, car 5000, imbalance..."
- Query: "images without person" -> لیست عکس‌های بدون عابر
- سپس Export فقط عکس‌های با کیفیت بالا (QA score >0.8)

### مثال کامل فارسی

```bash
# فرض کنید فقط عابر و ماشین می‌خواهید
python -m pro_annotator --project datasets/tehran_traffic \
  --model models/yolo11n.onnx \
  --batch-folder /data/tehran_street \
  --wanted-classes person,car \
  --llm-model models/llm/qwen2-0_5b-instruct-q4_0.gguf \
  --headless --export-format yolo --export-path datasets/tehran_traffic/export
```

خروجی export فقط شامل person, car است.
```

cat > pro-annotator/README.md <<'PY'
# see parent README
PY

# remove mistaken
rm pro-annotator/README.md
cat > pro-annotator/README.md <<'MD'
# Offline Pro Annotator — Professional AI-Assisted Labeling with Tiny LLM

حرفه‌ای، کاملاً آفلاین، خودکار و هوشمند.

## Quick Start

```bash
cd pro-annotator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

python scripts/download_models.py --yolo yolov8n
python scripts/download_llm.py --model qwen2-0.5b

python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx --offline
```

Features:

- Offline YOLO ONNX auto-label
- Batch folder thousands images, only wanted classes: --wanted-classes person,car
- Tiny LLM offline GGUF/ONNX/HF for label QA: --llm-model models/llm/qwen2-0_5b-instruct-q4_0.gguf
- YOLO/COCO/VOC export, video frame extraction
- Professional dark UI
- Dataset manager, validators, active learning

See docs/LLM_GUIDE.md and docs/BATCH_GUIDE.md
