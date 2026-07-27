from __future__ import annotations

import queue
import threading
import time
from collections import deque
from typing import Generic, TypeVar

from .vision_contracts import CapturedFrame, FrameMetadata


T = TypeVar("T")


class StreamEnded(Exception):
    pass


class DropOldestQueue(Generic[T]):
    """Bounded queue for realtime data: latency is preferred over old frames."""

    def __init__(self, maxsize: int = 2) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self._items: deque[T] = deque(maxlen=maxsize)
        self._condition = threading.Condition()
        self.dropped_count = 0

    def put(self, item: T) -> None:
        with self._condition:
            if len(self._items) == self._items.maxlen:
                self._items.popleft()
                self.dropped_count += 1
            self._items.append(item)
            self._condition.notify()

    def get(self, timeout: float | None = None) -> T:
        with self._condition:
            if not self._items and not self._condition.wait_for(lambda: bool(self._items), timeout):
                raise queue.Empty
            return self._items.popleft()

    def __len__(self) -> int:
        with self._condition:
            return len(self._items)


def validate_low_latency_pipeline(pipeline: str, sink_name: str = "camera_sink") -> tuple[str, ...]:
    problems: list[str] = []
    normalized = " ".join(pipeline.split())
    if "appsink" not in normalized or f"name={sink_name}" not in normalized:
        problems.append(f"pipeline must contain appsink name={sink_name}")
    if "max-buffers=1" not in normalized:
        problems.append("appsink must use max-buffers=1")
    if "drop=true" not in normalized and "leaky-type=downstream" not in normalized:
        problems.append("appsink must drop/leak old frames")
    if "queue" not in normalized or "leaky=downstream" not in normalized:
        problems.append("pipeline must contain a downstream-leaky queue")
    if "sync=false" not in normalized:
        problems.append("appsink must use sync=false")
    return tuple(problems)


def load_gstreamer() -> tuple[object, object, object]:
    try:
        import gi

        gi.require_version("Gst", "1.0")
        gi.require_version("GstApp", "1.0")
        gi.require_version("GstVideo", "1.0")
        from gi.repository import Gst, GstApp, GstVideo
    except (ImportError, ValueError) as exc:
        raise RuntimeError(
            "GStreamer Python runtime is missing; install python3-gi, gir1.2-gstreamer-1.0 "
            "and GStreamer plugins on the target host"
        ) from exc
    Gst.init(None)
    return Gst, GstApp, GstVideo


class GStreamerCamera:
    """appsink camera reader with an independent drop-oldest application queue."""

    def __init__(
        self,
        pipeline_description: str,
        stream_id: str,
        sink_name: str = "camera_sink",
        application_queue_size: int = 2,
    ) -> None:
        problems = validate_low_latency_pipeline(pipeline_description, sink_name)
        if problems:
            raise ValueError("; ".join(problems))
        self.pipeline_description = pipeline_description
        self.stream_id = stream_id
        self.sink_name = sink_name
        self.frames: DropOldestQueue[CapturedFrame] = DropOldestQueue(application_queue_size)
        self._sequence = 0
        self._pipeline = None
        self._gst = None
        self._gst_video = None
        self._bus = None
        self._terminal_error: RuntimeError | None = None
        self._eos = False

    def start(self) -> None:
        Gst, _, GstVideo = load_gstreamer()
        pipeline = Gst.parse_launch(self.pipeline_description)
        sink = pipeline.get_by_name(self.sink_name)
        if sink is None:
            raise RuntimeError(f"appsink {self.sink_name!r} was not created")
        sink.set_property("emit-signals", True)
        sink.connect("new-sample", self._on_sample)
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)
        self._gst = Gst
        self._gst_video = GstVideo
        self._bus = bus
        self._pipeline = pipeline
        result = pipeline.set_state(Gst.State.PLAYING)
        if result == Gst.StateChangeReturn.FAILURE:
            pipeline.set_state(Gst.State.NULL)
            self._pipeline = None
            raise RuntimeError("GStreamer camera pipeline failed to enter PLAYING")

    def _on_bus_message(self, _bus, message) -> None:
        Gst = self._gst
        if message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            self._terminal_error = RuntimeError(f"GStreamer input error: {error}; debug={debug or '-'}")
        elif message.type == Gst.MessageType.EOS:
            self._eos = True

    def _on_sample(self, sink):
        import numpy as np

        Gst = self._gst
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR
        buffer = sample.get_buffer()
        caps = sample.get_caps()
        structure = caps.get_structure(0)
        width = int(structure.get_value("width"))
        height = int(structure.get_value("height"))
        pixel_format = str(structure.get_value("format"))
        if pixel_format != "BGR":
            return Gst.FlowReturn.NOT_NEGOTIATED
        ok, mapped = buffer.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.ERROR
        try:
            info = self._gst_video.VideoInfo.new_from_caps(caps)
            stride = int(info.stride[0])
            raw = np.frombuffer(mapped.data, dtype=np.uint8).reshape(height, stride)
            image = raw[:, : width * 3].reshape(height, width, 3).copy()
        finally:
            buffer.unmap(mapped)
        now_monotonic_ms = time.monotonic_ns() // 1_000_000
        now_wall_ms = time.time_ns() // 1_000_000

        def clock_value(value: int) -> int | None:
            return None if value == Gst.CLOCK_TIME_NONE else int(value)

        metadata = FrameMetadata(
            stream_id=self.stream_id,
            sequence_no=self._sequence,
            host_monotonic_ms=now_monotonic_ms,
            captured_at_ms=now_wall_ms,
            width_px=width,
            height_px=height,
            pts_ns=clock_value(buffer.pts),
            dts_ns=clock_value(buffer.dts),
            duration_ns=clock_value(buffer.duration),
            pixel_format=pixel_format,
        )
        self._sequence += 1
        self.frames.put(CapturedFrame(metadata, image, dropped_before=self.frames.dropped_count))
        return Gst.FlowReturn.OK

    def read(self, timeout_s: float = 1.0) -> CapturedFrame:
        try:
            return self.frames.get(timeout_s)
        except queue.Empty as exc:
            if self._terminal_error is not None:
                raise self._terminal_error from exc
            if self._eos:
                raise StreamEnded("GStreamer input reached EOS") from exc
            raise TimeoutError(f"no camera frame received within {timeout_s:.3f}s") from exc

    def stop(self) -> None:
        if self._pipeline is not None and self._gst is not None:
            self._pipeline.set_state(self._gst.State.NULL)
        if self._bus is not None:
            self._bus.remove_signal_watch()
        self._bus = None
        self._pipeline = None


class NullFramePublisher:
    name = "null"

    def start(self) -> None:
        return None

    def publish(self, image, metadata: FrameMetadata) -> None:
        return None

    def stop(self) -> None:
        return None


class GStreamerFramePublisher:
    """Pushes annotated BGR frames to an appsrc encoder/output pipeline."""

    name = "gstreamer-appsrc"

    def __init__(self, pipeline_description: str, fps: float, source_name: str = "video_src") -> None:
        if "appsrc" not in pipeline_description or f"name={source_name}" not in pipeline_description:
            raise ValueError(f"output pipeline must contain appsrc name={source_name}")
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.pipeline_description = pipeline_description
        self.fps = fps
        self.source_name = source_name
        self._pipeline = None
        self._source = None
        self._gst = None
        self._sequence = 0

    def start(self) -> None:
        Gst, _, _ = load_gstreamer()
        pipeline = Gst.parse_launch(self.pipeline_description)
        source = pipeline.get_by_name(self.source_name)
        if source is None:
            raise RuntimeError(f"appsrc {self.source_name!r} was not created")
        result = pipeline.set_state(Gst.State.PLAYING)
        if result == Gst.StateChangeReturn.FAILURE:
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError("GStreamer output pipeline failed to enter PLAYING")
        self._gst, self._pipeline, self._source = Gst, pipeline, source

    def publish(self, image, metadata: FrameMetadata) -> None:
        if self._source is None or self._gst is None:
            raise RuntimeError("publisher is not started")
        payload = memoryview(image).tobytes()
        buffer = self._gst.Buffer.new_allocate(None, len(payload), None)
        buffer.fill(0, payload)
        duration = int(self._gst.SECOND / self.fps)
        buffer.pts = metadata.pts_ns if metadata.pts_ns is not None else self._sequence * duration
        buffer.dts = buffer.pts
        buffer.duration = duration
        result = self._source.emit("push-buffer", buffer)
        if result != self._gst.FlowReturn.OK:
            raise RuntimeError(f"appsrc push-buffer failed: {result}")
        self._sequence += 1

    def stop(self) -> None:
        if self._source is not None:
            self._source.emit("end-of-stream")
        if self._pipeline is not None and self._gst is not None:
            self._pipeline.set_state(self._gst.State.NULL)
        self._source = self._pipeline = None
