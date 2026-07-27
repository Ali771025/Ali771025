CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS video_runs (
    run_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_size_bytes INTEGER NOT NULL CHECK (source_size_bytes >= 0),
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    width_px INTEGER NOT NULL CHECK (width_px > 0),
    height_px INTEGER NOT NULL CHECK (height_px > 0),
    fps REAL NOT NULL CHECK (fps > 0),
    codec TEXT NOT NULL,
    backend TEXT NOT NULL,
    model_version TEXT NOT NULL,
    started_at_ms INTEGER NOT NULL,
    completed_at_ms INTEGER,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    error_message TEXT,
    created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS detections (
    detection_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES video_runs(run_id) ON DELETE CASCADE,
    frame_index INTEGER NOT NULL CHECK (frame_index >= 0),
    video_timestamp_ms INTEGER NOT NULL CHECK (video_timestamp_ms >= 0),
    class_id INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    x1_px REAL NOT NULL,
    y1_px REAL NOT NULL,
    x2_px REAL NOT NULL,
    y2_px REAL NOT NULL,
    track_id TEXT,
    depth_m REAL,
    depth_variance_m2 REAL,
    model_version TEXT NOT NULL,
    calibration_version TEXT,
    created_at_ms INTEGER NOT NULL,
    UNIQUE (run_id, frame_index, detection_id)
);

CREATE INDEX IF NOT EXISTS idx_detections_run_time
    ON detections(run_id, video_timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_detections_run_class
    ON detections(run_id, class_name);

CREATE TABLE IF NOT EXISTS world_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    created_at_ms INTEGER NOT NULL,
    pose_x_m REAL NOT NULL,
    pose_y_m REAL NOT NULL,
    heading_rad REAL NOT NULL,
    pose_timestamp_ms INTEGER NOT NULL,
    pose_quality REAL NOT NULL,
    pose_covariance_m2 REAL NOT NULL,
    frame_id TEXT NOT NULL,
    battery_percent REAL NOT NULL,
    battery_timestamp_ms INTEGER NOT NULL,
    source_sequence INTEGER NOT NULL,
    stale_sources_json TEXT NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS world_obstacles (
    snapshot_id TEXT NOT NULL REFERENCES world_snapshots(snapshot_id) ON DELETE CASCADE,
    obstacle_id TEXT NOT NULL,
    x_m REAL NOT NULL,
    y_m REAL NOT NULL,
    radius_m REAL NOT NULL,
    confidence REAL NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    position_variance_m2 REAL NOT NULL,
    PRIMARY KEY (snapshot_id, obstacle_id)
);

CREATE TABLE IF NOT EXISTS trajectories (
    trajectory_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    world_snapshot_id TEXT NOT NULL REFERENCES world_snapshots(snapshot_id),
    generated_at_ms INTEGER NOT NULL,
    control_authority TEXT NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trajectory_points (
    trajectory_id TEXT NOT NULL REFERENCES trajectories(trajectory_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    x_m REAL NOT NULL,
    y_m REAL NOT NULL,
    time_from_start_s REAL NOT NULL,
    speed_mps REAL NOT NULL,
    PRIMARY KEY (trajectory_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS safety_decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    trajectory_id TEXT NOT NULL REFERENCES trajectories(trajectory_id),
    evaluated_at_ms INTEGER NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('PASS', 'REJECT')),
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS safety_gate_results (
    decision_id INTEGER NOT NULL REFERENCES safety_decisions(decision_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    gate TEXT NOT NULL,
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    reason TEXT NOT NULL,
    observed_json TEXT,
    limit_json TEXT,
    PRIMARY KEY (decision_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    correlation_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_correlation_time
    ON audit_events(correlation_id, timestamp_ms);

