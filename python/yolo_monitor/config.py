from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional, Tuple, Union, Dict, Any
import yaml
from pydantic import BaseModel, Field, field_validator

class ModelConfig(BaseModel):
    path: str = "models/yolov8n.onnx"
    backend: str = "auto"
    task: str = "detect"

class TrackingConfig(BaseModel):
    enabled: bool = True
    tracker: str = "iou"
    iou_threshold: float = 0.3
    max_age: int = 30

class DrawConfig(BaseModel):
    labels: bool = True
    conf: bool = True
    track_id: bool = True
    center: bool = False
    box_coords: bool = False
    fps_overlay: bool = True
    line_thickness: int = 2
    font_scale: float = 0.5

class OutputConfig(BaseModel):
    show: bool = True
    save_video: Optional[str] = None
    log_path: Optional[str] = "detections.jsonl"
    log_format: str = "jsonl"
    log_per_frame: bool = False
    draw: DrawConfig = Field(default_factory=DrawConfig)

class ReconnectConfig(BaseModel):
    enabled: bool = True
    max_retries: int = 100
    backoff_base: float = 1.5
    initial_delay: float = 1.0
    max_delay: float = 30.0
    timeout_ms: int = 5000

class PipelineConfig(BaseModel):
    queue_size: int = 8
    drop_policy: str = "oldest"
    capture_fps: int = 30
    reconnect: ReconnectConfig = Field(default_factory=ReconnectConfig)

class SecretsConfig(BaseModel):
    env_user_var: str = "CAMERA_USER"
    env_pass_var: str = "CAMERA_PASSWORD"
    secrets_file: Optional[str] = None

class AppConfig(BaseModel):
    source: str = "0"
    source_type: str = "auto"
    model: ModelConfig = Field(default_factory=ModelConfig)
    device: str = "auto"
    imgsz: int = 640
    conf_thres: float = 0.35
    iou_thres: float = 0.45
    max_det: int = 300
    classes: List[int] = Field(default_factory=list)
    half: bool = False
    batch_size: int = 1
    warmup: int = 10
    frame_skip: int = 0
    roi: Optional[Tuple[int,int,int,int]] = None
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)
    offline: bool = False
    verbose: bool = False

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v):
        allowed = {"auto","usb","v4l2","rtsp","http","video","images","gstreamer","rtmp"}
        if v not in allowed:
            raise ValueError(f"source_type must be one of {allowed}")
        return v

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "AppConfig":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config not found: {path}")
        data = yaml.safe_load(p.read_text())
        return cls.model_validate(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        return cls.model_validate(data)

    def merge_cli(self, **kwargs: Any) -> "AppConfig":
        # kwargs may override nested keys using dot notation? simplified: only top-level and model.*
        d = self.model_dump()
        for k,v in kwargs.items():
            if v is None:
                continue
            if "." in k:
                parts = k.split(".")
                cur = d
                for pp in parts[:-1]:
                    cur = cur.setdefault(pp, {})
                cur[parts[-1]] = v
            else:
                # direct
                if k in d:
                    d[k] = v
                elif k in ("conf","iou","device","model_path","backend"):
                    mapping = {"conf":"conf_thres","iou":"iou_thres","device":"device","model_path":"model.path","backend":"model.backend"}
                    mk = mapping.get(k,k)
                    if "." in mk:
                        a,b = mk.split(".",1)
                        d[a][b]=v
                    else:
                        d[mk]=v
                else:
                    d[k]=v
        return AppConfig.model_validate(d)

def load_config(yaml_path: Optional[str], cli_overrides: Dict[str, Any]) -> AppConfig:
    if yaml_path:
        cfg = AppConfig.from_yaml(yaml_path)
    else:
        cfg = AppConfig()
    return cfg.merge_cli(**cli_overrides)
