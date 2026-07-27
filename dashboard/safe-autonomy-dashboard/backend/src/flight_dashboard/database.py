from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .auth import hash_password
from .models import Role
from .settings import Settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY,
  severity TEXT NOT NULL,
  code TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT NOT NULL,
  source TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  acknowledged_at_ms INTEGER,
  acknowledged_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at_ms DESC);
CREATE TABLE IF NOT EXISTS telemetry_samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  received_at_ms INTEGER NOT NULL,
  source TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_received ON telemetry_samples(received_at_ms DESC);
CREATE TABLE IF NOT EXISTS chat_messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  username TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_messages(conversation_id, created_at_ms);
CREATE TABLE IF NOT EXISTS control_intents (
  id TEXT PRIMARY KEY,
  idempotency_key TEXT UNIQUE NOT NULL,
  action TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_role TEXT NOT NULL,
  approved_by TEXT,
  approval_note TEXT,
  created_at_ms INTEGER NOT NULL,
  expires_at_ms INTEGER NOT NULL,
  executed_at_ms INTEGER,
  result_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_control_created ON control_intents(created_at_ms DESC);
CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  detail_json TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def initialize(self, settings: Settings) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            now = int(time.time() * 1000)
            users = (
                (settings.expert_username, "کارشناس پرواز", Role.FLIGHT_EXPERT.value, settings.expert_password),
                (settings.manager_username, "مدیر پرواز", Role.FLIGHT_MANAGER.value, settings.manager_password),
            )
            for username, name, role, password in users:
                exists = self._conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
                if not exists:
                    self._conn.execute(
                        "INSERT INTO users VALUES (?, ?, ?, ?, 1, ?)",
                        (username, name, role, hash_password(password), now),
                    )
            self._conn.commit()

    def one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._conn.execute(sql, params).fetchall()]

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def audit(self, actor: str, action: str, object_type: str, object_id: str, detail: dict[str, Any]) -> None:
        self.execute(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), actor, action, object_type, object_id, json.dumps(detail), int(time.time() * 1000)),
        )

    def save_alert(self, payload: dict[str, Any], source: str, created_at_ms: int) -> str:
        alert_id = str(payload.get("id") or uuid.uuid4())
        self.execute(
            "INSERT OR IGNORE INTO alerts (id,severity,code,title,detail,source,created_at_ms) VALUES (?,?,?,?,?,?,?)",
            (
                alert_id,
                payload.get("severity", "WARNING"),
                payload.get("code", "GENERIC"),
                payload.get("title", "هشدار سامانه"),
                payload.get("detail", ""),
                source,
                created_at_ms,
            ),
        )
        return alert_id

    def save_telemetry(self, source: str, payload: dict[str, Any], received_at_ms: int) -> None:
        self.execute(
            "INSERT INTO telemetry_samples(received_at_ms,source,payload_json) VALUES(?,?,?)",
            (received_at_ms, source, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

