from __future__ import annotations
import time
import threading
from typing import Optional
import cv2
import numpy as np

from ..config import AppConfig
from ..sources.factory import create_source
from ..detectors import create_detector
from ..tracking.simple_iou_tracker import IOUTracker
from ..logging.detection_logger import DetectionLogger
from ..utils.fps import FPSCounter, LatencyTracker
from ..utils.secrets import mask_url, expand_source_with_secrets
from .queues import BoundedQueue
from .types import FramePacket, InferencePacket

from loguru import logger

class DetectionPipeline:
    def __init__(self, config: AppConfig):
        self.config = config
        self.source_str = expand_source_with_secrets(
            config.source,
            env_user_var=config.secrets.env_user_var,
            env_pass_var=config.secrets.env_pass_var,
            secrets_file=config.secrets.secrets_file
        )
        self.masked_source = mask_url(self.source_str)
        self.source = create_source(self.source_str, source_type=config.source_type, timeout_ms=config.pipeline.reconnect.timeout_ms)
        self.detector = create_detector(
            model_path=config.model.path,
            backend=config.model.backend,
            device=config.device,
            imgsz=config.imgsz,
            conf_thres=config.conf_thres,
            iou_thres=config.iou_thres,
            max_det=config.max_det,
            classes=config.classes,
            half=config.half
        )
        self.tracker = IOUTracker(iou_threshold=config.tracking.iou_threshold, max_age=config.tracking.max_age) if config.tracking.enabled else None
        self.logger_writer = DetectionLogger(
            log_path=config.output.log_path,
            log_format=config.output.log_format,
            source_id=self.masked_source,
            source_type=config.source_type,
            model_name=config.model.path,
            device=config.device
        )

        self.capture_queue = BoundedQueue(maxsize=config.pipeline.queue_size, drop_policy=config.pipeline.drop_policy)
        self.inference_queue = BoundedQueue(maxsize=config.pipeline.queue_size, drop_policy=config.pipeline.drop_policy)
        self.render_queue = BoundedQueue(maxsize=config.pipeline.queue_size, drop_policy=config.pipeline.drop_policy)

        self.fps_counter = FPSCounter(window=30)
        self.inf_fps_counter = FPSCounter(window=30)
        self.latency_tracker = LatencyTracker(window=100)

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # not paused

        self.threads = []
        self.frame_id_counter = 0
        self.dropped_frames = 0
        self.source_status = "init"

        self.latest_result: Optional[InferencePacket] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.video_writer: Optional[cv2.VideoWriter] = None

        if config.output.save_video:
            self.video_writer = None  # initialized at first frame

    def start(self):
        logger.info(f"Starting pipeline: source={self.masked_source} model={self.config.model.path} device={self.config.device}")
        try:
            self.detector.load()
            self.detector.warmup(self.config.warmup)
        except Exception as e:
            logger.error(f"Detector load failed: {e}")
            raise

        # source open with reconnect logic
        if not self._open_source_with_retry():
            raise RuntimeError(f"Failed to open source: {self.masked_source}")

        # threads
        t_capture = threading.Thread(target=self._capture_loop, name="capture", daemon=True)
        t_inference = threading.Thread(target=self._inference_loop, name="inference", daemon=True)
        t_render = threading.Thread(target=self._render_loop, name="render", daemon=True)  # for video save maybe

        self.threads = [t_capture, t_inference, t_render]
        for t in self.threads:
            t.start()

    def _open_source_with_retry(self) -> bool:
        cfg = self.config.pipeline.reconnect
        retries = 0
        delay = cfg.initial_delay
        while not self.stop_event.is_set():
            ok = self.source.open()
            if ok:
                self.source_status = "ok"
                logger.info(f"Source opened: {self.masked_source}")
                return True
            else:
                self.source_status = f"failed: {self.source.last_error}"
                logger.warning(f"Failed to open source {self.masked_source}: {self.source.last_error} retry {retries}/{cfg.max_retries}")
                retries+=1
                if retries > cfg.max_retries:
                    return False
                time.sleep(delay)
                delay = min(delay*cfg.backoff_base, cfg.max_delay)
        return False

    def _capture_loop(self):
        consecutive_failures = 0
        while not self.stop_event.is_set():
            if not self.pause_event.is_set():
                time.sleep(0.01)
                continue
            ok, frame = self.source.read()
            if not ok or frame is None:
                consecutive_failures+=1
                self.source_status = f"read_fail {consecutive_failures}"
                logger.warning(f"Source read failed ({consecutive_failures}) for {self.masked_source}")
                # attempt reconnect if live
                if self.source.is_live() and self.config.pipeline.reconnect.enabled:
                    self.source.close()
                    time.sleep(self.config.pipeline.reconnect.initial_delay)
                    # try reopen
                    if not self._open_source_with_retry():
                        logger.error("Reconnect failed, stopping")
                        self.stop_event.set()
                        break
                    consecutive_failures=0
                    continue
                else:
                    # end of file / folder
                    logger.info("End of source")
                    time.sleep(0.1)
                    if not self.source.is_live():
                        # signal EOF
                        self.stop_event.set()
                        break
                    continue
            consecutive_failures=0
            self.source_status="ok"
            # ROI filtering
            if self.config.roi:
                x1,y1,x2,y2 = self.config.roi
                frame = frame[y1:y2, x1:x2]
            # frame skip
            if self.config.frame_skip>0:
                if self.frame_id_counter % (self.config.frame_skip+1) !=0:
                    self.frame_id_counter+=1
                    continue
            self.frame_id_counter+=1
            pkt = FramePacket(frame_id=self.frame_id_counter, frame=frame, timestamp_capture=time.time(), source_status=self.source_status)
            self.capture_queue.put(pkt)
            # control capture fps if needed
            # time.sleep(1.0/self.config.pipeline.capture_fps) optionally
        logger.info("Capture loop ended")

    def _inference_loop(self):
        while not self.stop_event.is_set():
            try:
                pkt: FramePacket = self.capture_queue.get(timeout=0.2)
            except Exception:
                continue
            try:
                t0 = time.time()
                result = self.detector.detect(pkt.frame, frame_id=pkt.frame_id)
                latency_ms = (time.time() - pkt.timestamp_capture)*1000.0
                self.latency_tracker.add(latency_ms)
                self.inf_fps_counter.tick()
                # tracking
                if self.tracker:
                    result.detections = self.tracker.update(result.detections)
                # logging
                self.logger_writer.log_detections(result, latency_ms=latency_ms)
                inf_pkt = InferencePacket(frame_packet=pkt, result=result, timestamp_inference_done=time.time())
                self.inference_queue.put(inf_pkt)
                self.latest_result = inf_pkt
                self.capture_queue.task_done()
            except Exception as e:
                logger.error(f"Inference error: {e}")
                self.capture_queue.task_done()

    def _render_loop(self):
        # Handles video writer if needed; otherwise just pass to render queue
        while not self.stop_event.is_set():
            try:
                pkt: InferencePacket = self.inference_queue.get(timeout=0.2)
            except Exception:
                continue
            try:
                # save video if needed
                if self.config.output.save_video and self.video_writer is None:
                    # init writer based on first frame
                    h,w = pkt.frame_packet.frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    self.video_writer = cv2.VideoWriter(self.config.output.save_video, fourcc, 30.0, (w,h))
                # we don't draw here, just forward to display
                self.render_queue.put(pkt)
                self.inference_queue.task_done()
            except Exception as e:
                logger.error(f"Render loop error: {e}")
                self.inference_queue.task_done()

    def get_latest(self, timeout: float = 0.1) -> Optional[InferencePacket]:
        try:
            return self.render_queue.get(timeout=timeout)
        except Exception:
            return None

    def stop(self):
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=1.0)
        try:
            self.source.close()
        except:
            pass
        try:
            self.logger_writer.close()
        except:
            pass
        if self.video_writer:
            try:
                self.video_writer.release()
            except:
                pass
        logger.info("Pipeline stopped")
