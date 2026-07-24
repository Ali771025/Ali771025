from __future__ import annotations
import sys
import time
import signal
from pathlib import Path
from typing import Optional
import cv2
import typer
from loguru import logger

from .config import AppConfig, load_config
from .pipeline import DetectionPipeline
from .ui.window_opencv import OpenCVMonitorWindow
from .utils.drawing import draw_detections, draw_overlay

app = typer.Typer(add_completion=False, help="Offline YOLO Monitor")

def version_callback(value: bool):
    if value:
        typer.echo("offline-yolo-monitor-annotator 1.0.0")
        raise typer.Exit()

@app.command()
def main(
    source: str = typer.Option("0", "--source", "-s", help="Source: 0, /dev/video0, rtsp://..., http://..., video.mp4, image folder, gstreamer pipeline"),
    source_type: str = typer.Option("auto", "--source-type", help="Source type: auto, usb, v4l2, rtsp, http, video, images, gstreamer"),
    model: str = typer.Option("models/yolov8n.onnx", "--model", "-m", help="Model path: .onnx, .pt, .engine"),
    backend: str = typer.Option("auto", "--backend", help="Backend: auto, onnx, tensorrt, ultralytics"),
    device: str = typer.Option("auto", "--device", help="Device: auto, cpu, cuda:0, tensorrt"),
    imgsz: int = typer.Option(640, "--imgsz", help="Image size"),
    conf: float = typer.Option(0.35, "--conf", help="Confidence threshold"),
    iou: float = typer.Option(0.45, "--iou", help="NMS IoU threshold"),
    max_det: int = typer.Option(300, "--max-det", help="Max detections"),
    classes: str = typer.Option("", "--classes", help="Class filter list e.g. 0,2,3"),
    half: bool = typer.Option(False, "--half", help="FP16"),
    show: bool = typer.Option(True, "--show/--no-show", help="Show live window"),
    save_video: Optional[str] = typer.Option(None, "--save-video", help="Save output video path"),
    log: Optional[str] = typer.Option("detections.jsonl", "--log", help="Log path: .csv or .jsonl"),
    log_format: str = typer.Option("jsonl", "--log-format", help="Log format: csv, jsonl, both, sqlite"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="YAML config file"),
    offline: bool = typer.Option(False, "--offline", help="Offline mode, no internet checks"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    frame_skip: int = typer.Option(0, "--frame-skip", help="Process every N+1 frames"),
):
    """
    Offline YOLO detection + monitoring
    Examples:
      python -m yolo_monitor --source 0 --model models/yolov8n.onnx --device cuda --show --log out.csv
      python -m yolo_monitor --source video.mp4 --model models/yolov8n.onnx --conf 0.35 --save-video out.mp4
    """
    # setup logging
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if verbose else "INFO")

    # parse classes
    class_list = []
    if classes:
        try:
            class_list = [int(x.strip()) for x in classes.split(",") if x.strip()!=""]
        except Exception:
            class_list=[]

    cli_overrides = {
        "source": source,
        "source_type": source_type,
        "model.path": model,
        "model.backend": backend,
        "device": device,
        "imgsz": imgsz,
        "conf_thres": conf,
        "iou_thres": iou,
        "max_det": max_det,
        "classes": class_list,
        "half": half,
        "output.show": show,
        "output.save_video": save_video,
        "output.log_path": log,
        "output.log_format": log_format,
        "offline": offline,
        "verbose": verbose,
        "frame_skip": frame_skip,
    }
    # filter None log? allow None
    if log is None or log.lower() in ("none","null",""):
        cli_overrides["output.log_path"]=None

    cfg = load_config(config_path, cli_overrides)

    # check model exists
    if not Path(cfg.model.path).exists():
        # maybe try to find in models/
        logger.warning(f"Model not found: {cfg.model.path}. If offline, ensure model exists. If online first time, run models/download_models.py")
        if not cfg.offline:
            logger.info("Attempting to continue, may fail at load time")

    pipeline = DetectionPipeline(cfg)

    stop_requested = False
    def handle_sigint(signum, frame):
        nonlocal stop_requested
        logger.info("SIGINT received, stopping...")
        stop_requested=True
        pipeline.stop()

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    try:
        pipeline.start()
    except Exception as e:
        logger.error(f"Failed to start pipeline: {e}")
        sys.exit(1)

    # UI loop
    window = None
    if cfg.output.show:
        # try Qt if requested? For now use OpenCV for lightweight
        window = OpenCVMonitorWindow(cfg, class_names=pipeline.detector.class_names)
        cv2.namedWindow(window.window_name, cv2.WINDOW_NORMAL)

    fps_counter = pipeline.fps_counter
    inf_fps_counter = pipeline.inf_fps_counter
    latency_tracker = pipeline.latency_tracker

    try:
        while not stop_requested:
            if pipeline.stop_event.is_set():
                logger.info("Pipeline stopped (EOF or error)")
                break

            pkt = pipeline.get_latest(timeout=0.1)
            if pkt is None:
                if window:
                    # still need waitKey to keep window responsive
                    key = cv2.waitKey(1) & 0xFF
                    if key != 255:
                        action = window.handle_keys(key)
                        if action == "quit":
                            break
                continue

            frame = pkt.frame_packet.frame.copy()
            result = pkt.result
            fps_counter.tick()
            fps = fps_counter.get_fps()
            inf_fps = inf_fps_counter.get_fps()
            latency_ms = (time.time() - pkt.frame_packet.timestamp_capture)*1000.0

            if window:
                # update conf thresholds live from window changes
                cfg.conf_thres = window.conf_thres
                cfg.iou_thres = window.iou_thres
                # adjust detector thresholds live
                pipeline.detector.conf_thres = window.conf_thres
                pipeline.detector.iou_thres = window.iou_thres

                frame_drawn = window.draw(frame, result, latency_ms, pipeline.source_status, fps, inf_fps)
                window.show(frame_drawn)
                key = cv2.waitKey(1) & 0xFF
                if key != 255:
                    action = window.handle_keys(key)
                    if action == "quit":
                        break
                    elif action == "pause":
                        pipeline.pause_event.clear()
                    elif action == "resume":
                        pipeline.pause_event.set()
                    elif action == "snapshot":
                        import datetime, os
                        os.makedirs("snapshots", exist_ok=True)
                        snap_path = f"snapshots/snap_{int(time.time())}.jpg"
                        cv2.imwrite(snap_path, frame)
                        logger.info(f"Snapshot saved: {snap_path}")
                    elif action == "conf_up":
                        logger.info(f"Conf threshold: {window.conf_thres:.2f}")
                    elif action == "conf_down":
                        logger.info(f"Conf threshold: {window.conf_thres:.2f}")
                # handle window close
                if cv2.getWindowProperty(window.window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
            else:
                # no window, just log FPS periodically
                if pipeline.frame_id_counter % 30 ==0:
                    logger.info(f"FPS: {fps:.1f} INF: {inf_fps:.1f} Lat: {latency_ms:.1f}ms Dets: {len(result.detections)} Status: {pipeline.source_status}")

            # save video if writer present (handled in pipeline rendering but we need to actually write)
            if pipeline.video_writer:
                # need to write frame with drawings? Save annotated if window else raw?
                if window:
                    pipeline.video_writer.write(frame_drawn)
                else:
                    # draw boxes before saving
                    from .utils.drawing import draw_detections, draw_overlay
                    tmp = draw_detections(frame.copy(), result.detections, class_names=pipeline.detector.class_names)
                    pipeline.video_writer.write(tmp)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        pipeline.stop()
        if window:
            window.close()
        cv2.destroyAllWindows()
        logger.info("Exit")

if __name__ == "__main__":
    app()
