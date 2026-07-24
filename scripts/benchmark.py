#!/usr/bin/env python3
"""
Benchmark detector FPS, latency p50/p95/p99
"""
import argparse
import time
import cv2
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, "python")
from yolo_monitor.detectors import create_detector
from yolo_monitor.utils.fps import FPSCounter, LatencyTracker

def main():
    parser = argparse.ArgumentParser(description="Benchmark YOLO detector")
    parser.add_argument("--model", type=str, required=True, help="Model path .onnx/.pt/.engine")
    parser.add_argument("--backend", type=str, default="auto")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--source", type=str, default=None, help="Video file or 0 for dummy, if None uses synthetic images")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--iters", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args()

    detector = create_detector(model_path=args.model, backend=args.backend, device=args.device, imgsz=args.imgsz, conf_thres=args.conf, iou_thres=args.iou)
    print(f"Loading model {args.model} backend {args.backend} device {args.device}")
    detector.load()
    detector.warmup(10)

    frames = []
    if args.source:
        cap = cv2.VideoCapture(args.source if not args.source.isdigit() else int(args.source))
        if not cap.isOpened():
            print(f"Failed to open source {args.source}, using dummy")
            frames = [np.zeros((720,1280,3), dtype=np.uint8) for _ in range(args.iters)]
        else:
            for _ in range(args.iters):
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES,0)
                    ret, frame = cap.read()
                frames.append(frame)
            cap.release()
    else:
        frames = [np.random.randint(0,255,(args.imgsz, args.imgsz,3), dtype=np.uint8) for _ in range(args.iters)]

    tracker = LatencyTracker(window=args.iters)
    fps_counter = FPSCounter(window=args.iters)

    print(f"Benchmarking {args.iters} iterations...")
    total_start = time.time()
    for i, frame in enumerate(frames):
        t0 = time.time()
        res = detector.detect(frame, frame_id=i)
        t1 = time.time()
        latency_ms = (t1-t0)*1000.0
        tracker.add(latency_ms)
        fps_counter.tick()
        if i % 10==0:
            print(f"  {i}/{args.iters} - {latency_ms:.1f}ms - {len(res.detections)} dets")

    total_time = time.time() - total_start
    avg_fps = args.iters / total_time if total_time>0 else 0
    print("\n=== Benchmark Results ===")
    print(f"Model: {args.model}")
    print(f"Backend: {args.backend} Device: {args.device} imgsz: {args.imgsz} batch: {args.batch_size}")
    print(f"Iterations: {args.iters}")
    print(f"Avg FPS: {avg_fps:.2f}")
    print(f"FPS (window): {fps_counter.get_fps():.2f}")
    print(f"Inference ms avg: {tracker.avg():.2f} p50: {tracker.p50():.2f} p95: {tracker.p95():.2f} p99: {tracker.p99():.2f}")
    # memory estimate
    try:
        import psutil, os
        proc = psutil.Process(os.getpid())
        mem_mb = proc.memory_info().rss / 1024/1024
        print(f"CPU RSS: {mem_mb:.1f} MB")
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            print(f"GPU mem allocated: {torch.cuda.memory_allocated()/1024/1024:.1f} MB")
    except Exception:
        pass

if __name__ == "__main__":
    main()
