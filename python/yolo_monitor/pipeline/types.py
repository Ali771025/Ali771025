from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
from ..detectors.base import FrameResult

@dataclass
class FramePacket:
    frame_id: int
    frame: np.ndarray
    timestamp_capture: float
    source_status: str = "ok"

@dataclass
class InferencePacket:
    frame_packet: FramePacket
    result: FrameResult
    timestamp_inference_done: float
