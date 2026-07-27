CREATE TABLE IF NOT EXISTS mission_maps (
    map_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_format TEXT NOT NULL CHECK (source_format IN ('GEOJSON', 'PGM', 'GEOTIFF', 'FIXTURE')),
    source_sha256 TEXT NOT NULL,
    source_size_bytes INTEGER NOT NULL CHECK (source_size_bytes >= 0),
    coordinate_system TEXT NOT NULL CHECK (coordinate_system IN ('LOCAL_ENU', 'WGS84_PROJECTED')),
    width_cells INTEGER NOT NULL CHECK (width_cells > 0),
    height_cells INTEGER NOT NULL CHECK (height_cells > 0),
    resolution_m REAL NOT NULL CHECK (resolution_m > 0),
    origin_x_m REAL NOT NULL,
    origin_y_m REAL NOT NULL,
    occupancy_blob BLOB NOT NULL,
    risk_blob BLOB NOT NULL,
    elevation_blob BLOB,
    analysis_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('VALID', 'DEGRADED', 'INVALID')),
    created_at_ms INTEGER NOT NULL,
    UNIQUE(source_sha256, resolution_m, origin_x_m, origin_y_m)
);

CREATE TABLE IF NOT EXISTS route_plan_requests (
    request_id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL REFERENCES mission_maps(map_id),
    start_x_m REAL NOT NULL,
    start_y_m REAL NOT NULL,
    goal_x_m REAL NOT NULL,
    goal_y_m REAL NOT NULL,
    start_altitude_m REAL NOT NULL,
    cruise_altitude_m REAL NOT NULL,
    policy_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    error_message TEXT,
    created_at_ms INTEGER NOT NULL,
    completed_at_ms INTEGER
);

CREATE TABLE IF NOT EXISTS route_candidates (
    candidate_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES route_plan_requests(request_id) ON DELETE CASCADE,
    rank_no INTEGER NOT NULL CHECK (rank_no > 0),
    total_cost REAL NOT NULL CHECK (total_cost >= 0),
    length_m REAL NOT NULL CHECK (length_m >= 0),
    estimated_duration_s REAL NOT NULL CHECK (estimated_duration_s >= 0),
    mean_risk REAL NOT NULL CHECK (mean_risk >= 0 AND mean_risk <= 1),
    minimum_clearance_m REAL,
    distinctness REAL NOT NULL CHECK (distinctness >= 0 AND distinctness <= 1),
    validation_status TEXT NOT NULL CHECK (validation_status IN ('VALID', 'REJECTED')),
    validation_reasons_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    UNIQUE(request_id, rank_no)
);

CREATE TABLE IF NOT EXISTS route_points (
    candidate_id TEXT NOT NULL REFERENCES route_candidates(candidate_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    cell_x INTEGER NOT NULL,
    cell_y INTEGER NOT NULL,
    x_m REAL NOT NULL,
    y_m REAL NOT NULL,
    altitude_m REAL NOT NULL,
    time_from_start_s REAL NOT NULL CHECK (time_from_start_s >= 0),
    cumulative_cost REAL NOT NULL CHECK (cumulative_cost >= 0),
    PRIMARY KEY(candidate_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS flight_assessments (
    assessment_id TEXT PRIMARY KEY,
    telemetry_frame_id TEXT REFERENCES telemetry_frames(telemetry_frame_id) ON DELETE SET NULL,
    sample_json TEXT NOT NULL,
    inferred_phase TEXT NOT NULL,
    previous_phase TEXT,
    transition_valid INTEGER NOT NULL CHECK (transition_valid IN (0, 1)),
    health_score REAL NOT NULL CHECK (health_score >= 0 AND health_score <= 100),
    highest_severity TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flight_findings (
    assessment_id TEXT NOT NULL REFERENCES flight_assessments(assessment_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    observed_json TEXT NOT NULL,
    limit_json TEXT NOT NULL,
    PRIMARY KEY(assessment_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS scenario_definitions (
    scenario_id TEXT NOT NULL,
    version TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    input_json TEXT NOT NULL,
    expected_json TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    PRIMARY KEY(scenario_id, version)
);

CREATE TABLE IF NOT EXISTS scenario_runs (
    run_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    scenario_version TEXT NOT NULL,
    started_at_ms INTEGER NOT NULL,
    completed_at_ms INTEGER NOT NULL,
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    actual_json TEXT NOT NULL,
    failure_reason TEXT,
    FOREIGN KEY(scenario_id, scenario_version) REFERENCES scenario_definitions(scenario_id, version)
);

CREATE TABLE IF NOT EXISTS scenario_events (
    run_id TEXT NOT NULL REFERENCES scenario_runs(run_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    PRIMARY KEY(run_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS idx_route_requests_map_time ON route_plan_requests(map_id, created_at_ms);
CREATE INDEX IF NOT EXISTS idx_flight_assessments_time ON flight_assessments(created_at_ms);
CREATE INDEX IF NOT EXISTS idx_scenario_runs_scenario_time ON scenario_runs(scenario_id, scenario_version, started_at_ms);
