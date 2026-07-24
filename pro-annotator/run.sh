#!/bin/bash
set -e
cd "$(dirname "$0")"
python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx --offline "$@"
