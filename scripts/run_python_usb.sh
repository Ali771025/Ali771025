#!/bin/bash
set -e
SCRIPT_DIR=$(cd $(dirname $0) && pwd)
ROOT=$(cd $SCRIPT_DIR/.. && pwd)
cd $ROOT
python -m yolo_monitor --source 0 --model models/yolov8n.onnx --device auto --show --log detections.jsonl "$@"
