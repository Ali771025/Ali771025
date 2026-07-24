#!/usr/bin/env python3
"""
One-time model downloader for pro-annotator (YOLO + SAM)
Offline after download.
"""
import argparse
from pathlib import Path
import urllib.request

MODEL_URLS = {
    "yolov8n": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.onnx",
    "yolov8s": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.onnx",
    "yolov8m": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8m.onnx",
    "yolo11n": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.onnx",
    "yolo11s": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.onnx",
    "mobile_sam": "https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt",
}

def download(url: str, dest: Path):
    print(f"Downloading {url} -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url) as resp, open(dest, 'wb') as out:
            total = resp.length
            dl=0
            while True:
                chunk=resp.read(8192)
                if not chunk:
                    break
                out.write(chunk)
                dl+=len(chunk)
                if total:
                    print(f"\r{dl}/{total} {dl/total*100:.1f}%", end="")
            print()
    except Exception as e:
        print(f"Failed {url}: {e}")
        if dest.exists():
            dest.unlink()
        raise

def main():
    parser = argparse.ArgumentParser(description="Download YOLO/SAM ONNX for offline pro-annotator")
    parser.add_argument("--yolo", type=str, default="yolov8n", help="Comma list: yolov8n,yolo11n,yolov8s,mobile_sam")
    parser.add_argument("--dest", type=str, default="models")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        for k,v in MODEL_URLS.items():
            print(f"{k}: {v}")
        return
    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for m in [x.strip() for x in args.yolo.split(",") if x.strip()]:
        if m not in MODEL_URLS:
            print(f"Unknown {m} skip")
            continue
        url = MODEL_URLS[m]
        ext = ".onnx" if m!="mobile_sam" else ".pt"
        dest = dest_dir / f"{m}{ext}"
        if dest.exists():
            print(f"Exists skip {dest}")
            continue
        try:
            download(url, dest)
        except Exception as e:
            print(f"Error {m}: {e} - place manually {dest}")

if __name__ == "__main__":
    main()
