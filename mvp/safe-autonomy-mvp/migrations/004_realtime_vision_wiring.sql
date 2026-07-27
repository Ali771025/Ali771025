ALTER TABLE telemetry_frames ADD COLUMN host_monotonic_ms INTEGER;

CREATE INDEX IF NOT EXISTS idx_telemetry_frames_monotonic
    ON telemetry_frames(host_monotonic_ms);

CREATE TABLE IF NOT EXISTS camera_streams (
    stream_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('V4L2', 'RTSP', 'FILE', 'TEST')),
    input_pipeline TEXT NOT NULL,
    output_pipeline TEXT,
    width_px INTEGER NOT NULL CHECK (width_px > 0),
    height_px INTEGER NOT NULL CHECK (height_px > 0),
    fps REAL NOT NULL CHECK (fps > 0),
    pixel_format TEXT NOT NULL,
    tracker_backend TEXT NOT NULL,
    model_version TEXT NOT NULL,
    configuration_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'STOPPED')),
    started_at_ms INTEGER NOT NULL,
    completed_at_ms INTEGER,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS vision_frames (
    vision_frame_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL REFERENCES camera_streams(stream_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    pts_ns INTEGER,
    dts_ns INTEGER,
    duration_ns INTEGER,
    host_monotonic_ms INTEGER NOT NULL,
    captured_at_ms INTEGER NOT NULL,
    width_px INTEGER NOT NULL CHECK (width_px > 0),
    height_px INTEGER NOT NULL CHECK (height_px > 0),
    capture_latency_ms REAL NOT NULL CHECK (capture_latency_ms >= 0),
    inference_latency_ms REAL NOT NULL CHECK (inference_latency_ms >= 0),
    publish_latency_ms REAL NOT NULL CHECK (publish_latency_ms >= 0),
    end_to_end_latency_ms REAL NOT NULL CHECK (end_to_end_latency_ms >= 0),
    dropped_before INTEGER NOT NULL CHECK (dropped_before >= 0),
    object_count INTEGER NOT NULL CHECK (object_count >= 0),
    status TEXT NOT NULL CHECK (status IN ('PROCESSED', 'DROPPED', 'FAILED')),
    UNIQUE(stream_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS idx_vision_frames_stream_time
    ON vision_frames(stream_id, host_monotonic_ms);

CREATE TABLE IF NOT EXISTS vision_objects (
    vision_frame_id TEXT NOT NULL REFERENCES vision_frames(vision_frame_id) ON DELETE CASCADE,
    object_id TEXT NOT NULL,
    track_id INTEGER,
    class_id INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    x1_px REAL NOT NULL,
    y1_px REAL NOT NULL,
    x2_px REAL NOT NULL,
    y2_px REAL NOT NULL,
    tracker_backend TEXT NOT NULL,
    PRIMARY KEY (vision_frame_id, object_id)
);

CREATE INDEX IF NOT EXISTS idx_vision_objects_track
    ON vision_objects(track_id, vision_frame_id);

CREATE TABLE IF NOT EXISTS sensor_vision_sync (
    sync_id TEXT PRIMARY KEY,
    vision_frame_id TEXT NOT NULL UNIQUE REFERENCES vision_frames(vision_frame_id) ON DELETE CASCADE,
    telemetry_frame_id TEXT REFERENCES telemetry_frames(telemetry_frame_id) ON DELETE SET NULL,
    skew_ms INTEGER,
    status TEXT NOT NULL CHECK (status IN ('MATCHED', 'TOO_OLD', 'MISSING')),
    policy_version TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS module_health_events (
    event_id TEXT PRIMARY KEY,
    module_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('STARTING', 'HEALTHY', 'DEGRADED', 'FAILED', 'STOPPED')),
    host_monotonic_ms INTEGER NOT NULL,
    latency_ms REAL NOT NULL CHECK (latency_ms >= 0),
    queue_depth INTEGER NOT NULL CHECK (queue_depth >= 0),
    dropped_count INTEGER NOT NULL CHECK (dropped_count >= 0),
    details_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_module_health_id_time
    ON module_health_events(module_id, host_monotonic_ms);

CREATE TABLE IF NOT EXISTS wiring_revisions (
    revision_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL UNIQUE,
    configuration_json TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('VALID', 'INVALID')),
    validation_reasons_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
);
