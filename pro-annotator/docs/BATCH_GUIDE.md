# Batch Guide - پردازش دسته‌ای فقط کلاس‌های دلخواه

## GUI
1. Tab Classes -> فقط person, car تیک بزنید
2. Tab Batch -> Browse Folder -> 10k عکس
3. Start Batch - فقط person, car لیبل می‌خورد

## CLI
python -m pro_annotator --project datasets/my --model models/yolov8n.onnx --batch-folder /path/to/images --wanted-classes person,car --conf 0.35

## Headless Export
python -m pro_annotator --project datasets/my --model models/yolov8n.onnx --batch-folder /data/images --wanted-classes person,car --headless --export-format yolo --export-path export/

فیلتر:
- set_wanted_classes(["person","car"])
- اگر خالی = ALL
- Threaded, autosave هر 50 عکس

ترکیب با LLM برای QA بعد از batch.
