#!/usr/bin/env python3
"""
One-time model downloader. Downloads YOLO ONNX models and optionally MobileSAM.
Works offline after download. No runtime telemetry.
"""
import argparse
import sys
from pathlib import Path
import urllib.request
import shutil

# URLs for YOLO models - using Ultralytics releases if internet available, otherwise user must provide manually
# We provide placeholders - attempt to download from Ultralytics GitHub releases for ONNX
MODEL_URLS = {
    "yolov8n": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.onnx",
    "yolov8s": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.onnx",
    "yolov8m": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8m.onnx",
    "yolo11n": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.onnx",
    "yolo11s": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.onnx",
    "yolo11m": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11m.onnx",
    "mobile_sam": "https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt",  # we need ONNX version; user may convert
}

def download(url: str, dest: Path):
    print(f"Downloading {url} -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        # use urllib with progress
        with urllib.request.urlopen(url) as response, open(dest, 'wb') as out:
            total = response.length
            downloaded=0
            chunk=8192
            while True:
                data=response.read(chunk)
                if not data:
                    break
                out.write(data)
                downloaded+=len(data)
                if total:
                    print(f"\r{downloaded}/{total} ({downloaded/total*100:.1f}%)", end="")
            print()
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        if dest.exists():
            dest.unlink()
        raise

def main():
    parser = argparse.ArgumentParser(description="Download ONNX models for offline use")
    parser.add_argument("--yolo", type=str, default="yolov8n", help="Comma-separated list of yolo models: yolov8n,yolov8s,yolo11n,yolo11s,mobile_sam")
    parser.add_argument("--dest", type=str, default="models", help="Destination folder")
    parser.add_argument("--list", action="store_true", help="List available models")
    args = parser.parse_args()

    if args.list:
        print("Available:")
        for k,v in MODEL_URLS.items():
            print(f"  {k}: {v}")
        return

    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)

    models = [m.strip() for m in args.yolo.split(",") if m.strip()]
    for m in models:
        if m not in MODEL_URLS:
            print(f"Unknown model {m}, available: {list(MODEL_URLS.keys())}")
            continue
        url = MODEL_URLS[m]
        ext = ".onnx" if not m.endswith("sam") else ".pt"
        if m=="mobile_sam":
            ext=".pt"
        dest = dest_dir / f"{m}{ext}"
        if dest.exists():
            print(f"Exists, skipping: {dest}")
            continue
        try:
            download(url, dest)
            print(f"Saved {dest}")
        except Exception as e:
            print(f"Error downloading {m}: {e}. You can manually place ONNX file at {dest}")

    print("Done. Models ready for offline use.")

if __name__ == "__main__":
    main()
