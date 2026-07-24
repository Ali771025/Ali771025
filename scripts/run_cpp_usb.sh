#!/bin/bash
set -e
SCRIPT_DIR=$(cd $(dirname $0) && pwd)
ROOT=$(cd $SCRIPT_DIR/.. && pwd)
cd $ROOT
if [ ! -f build/yolo_app ]; then
  echo "Build first: cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j"
  exit 1
fi
./build/yolo_app --source 0 --model models/yolov8n.onnx --device cpu --show --log detections.csv "$@"
