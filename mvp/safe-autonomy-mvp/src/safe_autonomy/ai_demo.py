from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from importlib.metadata import distribution
from pathlib import Path

from .advisory import AdvisoryRepository, DeterministicDecisionEngine, EvidenceGate, OllamaAdvisoryClient
from .coordinator import DecisionCoordinator
from .database import Database
from .hybrid_rag import HashingEmbedder, HybridRagEngine, KnowledgeStore, TokenOverlapReranker
from .sensor_contracts import (
    BarometerSample,
    BatterySample,
    GpsSample,
    ImuSample,
    PerceptionObject,
    SensorHeader,
    SensorKind,
)
from .sensor_fusion import TelemetrySynchronizer
from .telemetry_repository import TelemetryRepository


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _sample_sop_path() -> Path:
    source_path = PROJECT_ROOT / "knowledge" / "sample_sop_fa.md"
    if source_path.is_file():
        return source_path
    return Path(distribution("safe-autonomy-mvp").locate_file("safe_autonomy_knowledge/sample_sop_fa.md"))


def _sections(path: Path) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current = "مقدمه"
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if lines:
                sections.append((current, "\n".join(lines).strip()))
            current = line[3:].strip()
            lines = []
        elif not line.startswith("# "):
            lines.append(line)
    if lines:
        sections.append((current, "\n".join(lines).strip()))
    return [(section, content) for section, content in sections if content]


def _seed_knowledge(store: KnowledgeStore) -> None:
    document_id = store.add_document(
        source_id="SOP-DEV-001",
        title="SOP پژوهشی مدیریت داده و رخداد",
        version="1.0",
        sections=_sections(_sample_sop_path()),
    )
    rows = store.database.connection.execute(
        "SELECT chunk_id, section FROM knowledge_chunks WHERE document_id=?", (document_id,)
    ).fetchall()
    by_section = {str(row[1]): str(row[0]) for row in rows}
    yolo = store.add_node("component:yolo", "COMPONENT", "YOLO", ("تشخیص شیء", "detection"))
    depth = store.add_node("signal:depth", "SIGNAL", "Depth", ("عمق", "فاصله"))
    ttc = store.add_node("metric:ttc", "METRIC", "TTC", ("زمان برخورد", "Time to Collision"))
    gps = store.add_node("sensor:gps", "SENSOR", "GPS", ("GNSS",))
    hold = store.add_node("intent:hold", "INTENT", "HOLD", ("توقف ایمن",))
    store.add_edge(yolo, depth, "REQUIRES", by_section["ادراک"])
    store.add_edge(depth, ttc, "ENABLES", by_section["ادراک"])
    store.add_edge(gps, hold, "STALE_TRIGGERS", by_section["داده ناهمگام"])


def run_demo(database_path: str | Path, scenario: str = "incomplete_depth", use_ollama: bool = False) -> dict:
    now_ms = 20_000
    sensor_time = now_ms - 1_000 if scenario == "stale" else now_ms
    battery_percent = 10.0 if scenario == "low_battery" else 80.0
    synchronizer = TelemetrySynchronizer(35.7000, 51.3000, 1_200.0)
    synchronizer.update(SensorKind.GPS, GpsSample(
        SensorHeader(sensor_time, 1, "px4-gps", "wgs84", 0.95, "gps-cal-v1"),
        35.7001, 51.3001, 1_230.0, 2.0, 0.5, 0.0, 0.8, 1.2, 3,
    ))
    synchronizer.update(SensorKind.IMU, ImuSample(
        SensorHeader(sensor_time, 1, "px4-imu", "base_link", 0.98, "imu-cal-v2"),
        (0.0, 0.0, 9.81), (0.01, 0.01, 0.02), 42.0,
    ))
    synchronizer.update(SensorKind.BAROMETER, BarometerSample(
        SensorHeader(sensor_time, 1, "px4-baro", "base_link", 0.92, "baro-cal-v1"),
        87_000.0, 30.5, 0.25,
    ))
    synchronizer.update(SensorKind.BATTERY, BatterySample(
        SensorHeader(sensor_time, 1, "px4-battery", "base_link", 0.99),
        battery_percent, 15.2, 8.0, 38.0,
    ))
    if scenario == "incomplete_depth":
        synchronizer.update_perception((PerceptionObject(
            "yolo-1", "airplane", 0.91, now_ms, (40.0, 30.0, 330.0, 200.0), track_id="track-1",
        ),))
    elif scenario == "bounded_ttc":
        synchronizer.update_perception((PerceptionObject(
            "yolo-1", "airplane", 0.91, now_ms, (40.0, 30.0, 330.0, 200.0),
            track_id="track-1", depth_m=40.0, depth_variance_m2=4.0,
            relative_velocity_mps=-10.0, ttc_s=4.0,
        ),))
    frame = synchronizer.snapshot(now_ms)

    database = Database(database_path)
    database.migrate()
    telemetry_repository = TelemetryRepository(database)
    telemetry_repository.save_synchronizer(synchronizer, frame)
    knowledge_store = KnowledgeStore(database, HashingEmbedder(128))
    _seed_knowledge(knowledge_store)
    rag_engine = HybridRagEngine(knowledge_store, rrf_k=60, reranker=TokenOverlapReranker())
    llm = OllamaAdvisoryClient("safe-advisory-qwen3-4b") if use_ollama else None
    coordinator = DecisionCoordinator(
        DeterministicDecisionEngine(), rag_engine, EvidenceGate(),
        AdvisoryRepository(database), llm,
    )
    result = coordinator.evaluate(f"demo-{scenario}", frame, now_ms)
    output = {
        "scenario": scenario,
        "telemetry_frame_id": frame.telemetry_frame_id,
        "stale_sources": frame.stale_sources,
        "decision": asdict(result.deterministic_decision),
        "proposal": asdict(result.proposal),
        "evidence_gate": asdict(result.gate),
        "evidence": [
            {
                "chunk_id": item.chunk_id, "source_id": item.source_id,
                "section": item.section, "score": item.fused_score,
                "channels": item.channels,
            }
            for item in result.rag_result.evidence
        ],
    }
    database.close()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GPS/IMU/YOLO + Hybrid RAG + KG advisory demo")
    parser.add_argument("--database", default="artifacts/ai_dev_v0.3.sqlite3")
    parser.add_argument("--scenario", choices=("nominal", "incomplete_depth", "bounded_ttc", "stale", "low_battery"), default="incomplete_depth")
    parser.add_argument("--ollama", action="store_true", help="Call local Ollama instead of deterministic advisory")
    args = parser.parse_args()
    print(json.dumps(run_demo(args.database, args.scenario, args.ollama), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
