from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Protocol

from .contracts import AuditEvent


class AuditSink(Protocol):
    def append(self, event: AuditEvent) -> None: ...


class JsonlAuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append(self, event: AuditEvent) -> None:
        encoded = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(encoded + "\n")


class CompositeAuditLog:
    def __init__(self, *sinks: AuditSink) -> None:
        self.sinks = sinks

    def append(self, event: AuditEvent) -> None:
        for sink in self.sinks:
            sink.append(event)


class DatabaseAuditLog:
    def __init__(self, repository) -> None:
        self.repository = repository

    def append(self, event: AuditEvent) -> None:
        self.repository.save_audit_event(event)
