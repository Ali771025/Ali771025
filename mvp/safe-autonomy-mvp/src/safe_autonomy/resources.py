from __future__ import annotations

from importlib.metadata import distribution
from pathlib import Path


def resolve_resource(path: str | Path, installed_directory: str) -> Path:
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    try:
        installed = Path(distribution("safe-autonomy-mvp").locate_file(installed_directory)) / candidate.name
    except Exception:
        return candidate
    return installed if installed.is_file() else candidate
