CREATE TABLE IF NOT EXISTS temporal_observations (
    observation_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    source_monotonic_ms INTEGER NOT NULL,
    received_monotonic_ms INTEGER NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('ACCEPT', 'DEGRADED', 'REJECT')),
    age_ms INTEGER NOT NULL,
    cross_source_skew_ms INTEGER,
    reasons_json TEXT NOT NULL,
    UNIQUE(source, sequence_no)
);

CREATE TABLE IF NOT EXISTS system_readiness_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (state IN ('READY', 'DEGRADED', 'NOT_READY')),
    score REAL NOT NULL CHECK (score BETWEEN 0 AND 100),
    gates_json TEXT NOT NULL,
    evaluated_monotonic_ms INTEGER NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS energy_assessments (
    assessment_id TEXT PRIMARY KEY,
    feasible INTEGER NOT NULL CHECK (feasible IN (0, 1)),
    estimated_energy_wh REAL NOT NULL,
    available_energy_wh REAL NOT NULL,
    reserve_energy_wh REAL NOT NULL,
    margin_wh REAL NOT NULL,
    wind_penalty_ratio REAL NOT NULL,
    gates_json TEXT NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_revalidations (
    assessment_id TEXT PRIMARY KEY,
    route_candidate_id TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    cross_track_error_m REAL NOT NULL,
    progress_ratio REAL NOT NULL CHECK (progress_ratio BETWEEN 0 AND 1),
    remaining_distance_m REAL NOT NULL,
    corridor_risk REAL NOT NULL CHECK (corridor_risk BETWEEN 0 AND 1),
    reasons_json TEXT NOT NULL,
    evaluated_monotonic_ms INTEGER NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assurance_reports (
    report_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    overall_status TEXT NOT NULL CHECK (overall_status IN ('PASS', 'WARN', 'FAIL')),
    readiness_snapshot_id TEXT NOT NULL REFERENCES system_readiness_snapshots(snapshot_id),
    energy_assessment_id TEXT NOT NULL REFERENCES energy_assessments(assessment_id),
    gates_json TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS latency_slo_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_temporal_source_time ON temporal_observations(source, received_monotonic_ms);
CREATE INDEX IF NOT EXISTS idx_readiness_time ON system_readiness_snapshots(evaluated_monotonic_ms);
CREATE INDEX IF NOT EXISTS idx_revalidation_route_time ON route_revalidations(route_candidate_id, evaluated_monotonic_ms);
CREATE INDEX IF NOT EXISTS idx_assurance_mission_time ON assurance_reports(mission_id, created_at_ms);
