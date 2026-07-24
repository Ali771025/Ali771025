# Offline Pro Annotator 2.0 — Professional AI + Batch + Tiny LLM (Persian + English)

**حرفه‌ای، ۱۰۰٪ آفلاین، Batch هزاران عکس فقط کلاس‌های دلخواه، Tiny LLM GGUF/ONNX آفلاین برای QA**

## نصب سریع + GPU

```bash
cd pro-annotator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pip install PySide6

# CPU LLM GGUF
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
# GPU LLM (transformers + torch CUDA 12.1)
pip install transformers accelerate torch --index-url https://download.pytorch.org/whl/cu121

python scripts/download_models.py --yolo yolov8n --dest ../models
python scripts/download_llm.py --model qwen2-0.5b --dest models/llm
# گزینه‌ها: qwen2-0.5b 0.4GB فارسی عالی سریعترین (توصیه), qwen2-1.5b 1GB بهتر, tinyllama 0.6GB, phi-2 1.6GB, phi-3-mini 2.2GB
```

## اجرای GUI

```bash
# بدون LLM (heuristic dummy همیشه کار)
python -m pro_annotator --project datasets/my_dataset --model ../models/yolov8n.onnx --offline

# با LLM GGUF فارسی
python -m pro_annotator --project datasets/my_dataset \
  --model ../models/yolov8n.onnx \
  --llm-model models/llm/qwen2-0_5b-instruct-q4_0.gguf --llm-backend llama_cpp --offline

# با LLM GPU transformers
python -m pro_annotator --project datasets/my \
  --model ../models/yolov8n.onnx \
  --llm-model models/llm/Qwen2-0.5B-Instruct --llm-backend transformers --device cuda --offline
```

**داخل UI:**
- Tab Images: thumbnail + search + QA ⚠️
- Tab Classes: چک‌باکس Wanted Classes - فقط person,car تیک بزن → بقیه نادیده (empty = ALL)
- Tab Batch: Browse Folder 10k عکس → Start Batch (فقط wanted, thread جدا, progress, autosave هر 50)
- Tab LLM QA: Load LLM → Analyze Current Image (duplicate/tiny/oob) → Analyze Dataset (توزیع/imbalance) → Query فارسی `عکس‌هایی که ماشین ندارند`
- Canvas: drag ساخت bbox، move، zoom wheel، Ctrl+drag pan، Del حذف

## Batch فقط کلاس‌های دلخواه - هزاران عکس

```bash
# GUI
# Tab Classes: person,car تیک → Tab Batch: /data/images → Start

# CLI
python -m pro_annotator --project datasets/my \
  --model ../models/yolov8n.onnx \
  --batch-folder /data/10000_images --wanted-classes person,car --conf 0.4 --recursive --offline

# Headless + LLM QA + Export
python -m pro_annotator --project datasets/tehran_traffic \
  --model ../models/yolo11n.onnx \
  --batch-folder /data/tehran_street --wanted-classes person,car \
  --llm-model models/llm/qwen2-0_5b-instruct-q4_0.gguf --llm-backend llama_cpp \
  --headless --export-format yolo --export-path datasets/tehran_traffic/export --offline
# خروجی: export_yolo/labels/*.txt فقط person,car + llm_report.json + dataset_stats.json
```

## LLM - تحلیل لیبل

**Backend ها:**
- `llama_cpp`: GGUF 0.4-2GB CPU بهینه - `pip install llama-cpp-python` - توصیه برای CPU
- `transformers`: HF folder محلی + torch CUDA برای GPU - `pip install transformers accelerate torch`
- `onnx`: ONNX Runtime LLM via optimum - `pip install optimum[onnxruntime]`
- `dummy`: بدون مدل، heuristic: duplicate IoU>0.95, tiny <8px, out_of_bounds, low_conf - همیشه کار

**قابلیت‌ها:**
```python
llm = LLMAnalyzer(model_path="models/llm/qwen2-0_5b-instruct-q4_0.gguf", backend="llama_cpp")
llm.load()
result = llm.analyze_image_labels(ann) # issues, suggestions, qa_score, description فارسی/انگلیسی
report = llm.analyze_dataset(images) # توزیع کلاس، imbalance، merge پیشنهاد
answer = llm.query_dataset("عکس‌هایی که بیش از 3 ماشین دارند", images)
mapping = llm.suggest_class_mapping(["car","truck"], "merge car and truck into vehicle")
```

## GPU توسعه

- YOLO: `device=cuda` + `half=True` برای FP16 - 30-60 FPS
- LLM: transformers backend با `device=cuda` + torch CUDA
- Qwen2-0.5B GPU نیاز VRAM ~1GB، Qwen2-1.5B ~3GB

```bash
# YOLO GPU
python -m pro_annotator --project datasets/my --model ../models/yolov8n.onnx --device cuda --offline

# LLM GPU transformers
python -m pro_annotator --project datasets/my --model ../models/yolov8n.onnx \
  --llm-model models/llm/Qwen2-0.5B-Instruct --llm-backend transformers --device cuda
```

## Docs

- `docs/LLM_GUIDE.md`: تمام جزئیات LLM
- `docs/BATCH_GUIDE.md`: Batch فقط wanted
- `configs/annotator.yaml`: کلاس‌ها، مدل‌ها، llm, batch, ui

## تست

```bash
pytest tests -v
```

## بالا آوردن سرویس

برای batch headless می‌توانی cron یا systemd بسازی.

MIT - 100% آفلاین
