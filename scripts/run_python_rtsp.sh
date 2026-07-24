#!/bin/bash
set -e
SCRIPT_DIR=$(cd $(dirname $0) && pwd)
ROOT=$(cd $SCRIPT_DIR/.. && pwd)
cd $ROOT
: ${CAMERA_USER:?Set CAMERA_USER env}
: ${CAMERA_PASSWORD:?Set CAMERA_PASSWORD env}
: ${RTSP_URL:?Set RTSP_URL e.g. rtsp://ip:554/stream}
# expand credentials if URL contains placeholders
URL=$(echo $RTSP_URL | sed "s/CAMERA_USER/$CAMERA_USER/g" | sed "s/CAMERA_PASSWORD/$CAMERA_PASSWORD/g")
python -m yolo_monitor --source "$URL" --model models/yolov8n.onnx --device auto --show --log rtsp_detections.jsonl "$@"
