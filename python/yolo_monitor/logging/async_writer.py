from __future__ import annotations
import queue
import threading
import csv
import json
from pathlib import Path
from typing import Optional, Dict, Any
import time

class AsyncWriter:
    def __init__(self, path: str, format: str = "jsonl", buffer_size: int = 1000):
        self.path = Path(path)
        self.format = format.lower()
        self.queue: queue.Queue = queue.Queue(maxsize=buffer_size)
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self._file_handle = None
        self._csv_writer = None
        self._header_written = False

    def start(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.format == "csv":
            self._file_handle = open(self.path, "w", newline="", encoding="utf-8")
        elif self.format in ("jsonl","json"):
            self._file_handle = open(self.path, "w", encoding="utf-8")
        elif self.format == "both":
            # will write both csv and jsonl: use two files
            self._file_handle = open(self.path, "w", encoding="utf-8")
            # csv parallel
            csv_path = self.path.with_suffix(".csv")
            self._csv_file = open(csv_path, "w", newline="", encoding="utf-8")
            self._csv_writer = None
        elif self.format == "sqlite":
            import sqlite3
            self._conn = sqlite3.connect(str(self.path))
            self._cursor = self._conn.cursor()
            self._create_sqlite_table()
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _create_sqlite_table(self):
        self._cursor.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            timestamp_unix REAL,
            timestamp_iso TEXT,
            source_id TEXT,
            source_type TEXT,
            frame_id INTEGER,
            frame_width INTEGER,
            frame_height INTEGER,
            model_name TEXT,
            device TEXT,
            class_id INTEGER,
            class_name TEXT,
            confidence REAL,
            x1 REAL, y1 REAL, x2 REAL, y2 REAL,
            x REAL, y REAL, w REAL, h REAL,
            cx REAL, cy REAL, nw REAL, nh REAL,
            center_x REAL, center_y REAL,
            area REAL, aspect_ratio REAL,
            track_id INTEGER,
            inference_time_ms REAL,
            latency_ms REAL
        )
        """)
        self._conn.commit()

    def _run(self):
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if self.format == "csv":
                    self._write_csv_item(item)
                elif self.format in ("jsonl","json"):
                    self._file_handle.write(json.dumps(item)+"\n")
                    self._file_handle.flush()
                elif self.format == "both":
                    self._file_handle.write(json.dumps(item)+"\n")
                    self._file_handle.flush()
                    self._write_csv_item(item, file_handle=self._csv_file)
                elif self.format == "sqlite":
                    self._write_sqlite_item(item)
            except Exception as e:
                # avoid crashing writer thread
                print(f"Writer error: {e}")
            finally:
                self.queue.task_done()

    def _write_csv_item(self, item: Dict[str, Any], file_handle=None):
        fh = file_handle or self._file_handle
        if self._csv_writer is None:
            # need header
            fieldnames = list(item.keys())
            self._csv_writer = csv.DictWriter(fh, fieldnames=fieldnames)
            self._csv_writer.writeheader()
            self._header_written = True
        else:
            # handle missing keys
            # if new keys appear, ignore? For simplicity require same keys
            pass
        try:
            self._csv_writer.writerow(item)
            fh.flush()
        except Exception:
            # if header mismatch, rewrite?
            pass

    def _write_sqlite_item(self, item: Dict[str, Any]):
        cols = ["timestamp_unix","timestamp_iso","source_id","source_type","frame_id","frame_width","frame_height","model_name","device","class_id","class_name","confidence","x1","y1","x2","y2","x","y","w","h","cx","cy","nw","nh","center_x","center_y","area","aspect_ratio","track_id","inference_time_ms","latency_ms"]
        # map from item keys to sqlite cols
        mapping = {
            "timestamp_unix": item.get("timestamp_unix"),
            "timestamp_iso": item.get("timestamp_iso"),
            "source_id": item.get("source_id"),
            "source_type": item.get("source_type"),
            "frame_id": item.get("frame_id"),
            "frame_width": item.get("frame_width"),
            "frame_height": item.get("frame_height"),
            "model_name": item.get("model_name"),
            "device": item.get("device"),
            "class_id": item.get("class_id"),
            "class_name": item.get("class_name"),
            "confidence": item.get("confidence"),
            "x1": item.get("x1"),
            "y1": item.get("y1"),
            "x2": item.get("x2"),
            "y2": item.get("y2"),
            "x": item.get("x"),
            "y": item.get("y"),
            "w": item.get("w"),
            "h": item.get("h"),
            "cx": item.get("cx"),
            "cy": item.get("cy"),
            "nw": item.get("nw"),
            "nh": item.get("nh"),
            "center_x": item.get("center_x"),
            "center_y": item.get("center_y"),
            "area": item.get("area"),
            "aspect_ratio": item.get("aspect_ratio"),
            "track_id": item.get("track_id"),
            "inference_time_ms": item.get("inference_time_ms"),
            "latency_ms": item.get("latency_ms"),
        }
        placeholders = ",".join(["?"]*len(cols))
        self._cursor.execute(f"INSERT INTO detections ({','.join(cols)}) VALUES ({placeholders})", [mapping.get(c) for c in cols])
        self._conn.commit()

    def write(self, item: Dict[str, Any]):
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            # drop oldest if full?
            try:
                self.queue.get_nowait()
            except:
                pass
            try:
                self.queue.put_nowait(item)
            except:
                pass

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        if self._file_handle:
            try:
                self._file_handle.close()
            except:
                pass
        if hasattr(self, '_csv_file'):
            try:
                self._csv_file.close()
            except:
                pass
        if hasattr(self, '_conn'):
            try:
                self._conn.close()
            except:
                pass
