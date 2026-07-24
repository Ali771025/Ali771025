# Python implementation

## Install
pip install -r requirements.txt
pip install -e .

## Run monitor
python -m yolo_monitor --source 0 --model ../models/yolov8n.onnx --device cpu --show --log detections.jsonl

## Run annotator
python -m yolo_annotator --project ../datasets/my_dataset --model ../models/yolov8n.onnx --offline

## Tests
pytest tests -v
