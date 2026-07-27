CREATE TABLE IF NOT EXISTS telemetry_samples (
    sample_id TEXT PRIMARY KEY,
    sensor_kind TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    sequence_no INTEGER NOT NULL,
    source TEXT NOT NULL,
    frame_id TEXT NOT NULL,
    quality REAL NOT NULL CHECK (quality >= 0 AND quality <= 1),
    calibration_version TEXT,
    payload_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_kind_time
    ON telemetry_samples(sensor_kind, timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_telemetry_source_sequence
    ON telemetry_samples(source, sequence_no);

CREATE TABLE IF NOT EXISTS telemetry_frames (
    telemetry_frame_id TEXT PRIMARY KEY,
    created_at_ms INTEGER NOT NULL,
    local_x_m REAL NOT NULL,
    local_y_m REAL NOT NULL,
    altitude_m REAL NOT NULL,
    velocity_north_mps REAL NOT NULL,
    velocity_east_mps REAL NOT NULL,
    velocity_down_mps REAL NOT NULL,
    battery_percent REAL NOT NULL,
    overall_quality REAL NOT NULL CHECK (overall_quality >= 0 AND overall_quality <= 1),
    timestamp_skew_ms INTEGER NOT NULL,
    stale_sources_json TEXT NOT NULL,
    source_sample_ids_json TEXT NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_perception_objects (
    telemetry_frame_id TEXT NOT NULL REFERENCES telemetry_frames(telemetry_frame_id) ON DELETE CASCADE,
    object_id TEXT NOT NULL,
    class_name TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    timestamp_ms INTEGER NOT NULL,
    bbox_json TEXT NOT NULL,
    track_id TEXT,
    depth_m REAL,
    depth_variance_m2 REAL,
    relative_velocity_mps REAL,
    ttc_s REAL,
    PRIMARY KEY (telemetry_frame_id, object_id)
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    version TEXT NOT NULL,
    checksum TEXT NOT NULL,
    authority_status TEXT NOT NULL CHECK (authority_status IN ('AUTHORITATIVE', 'REFERENCE', 'UNTRUSTED')),
    valid_from_ms INTEGER,
    valid_to_ms INTEGER,
    created_at_ms INTEGER NOT NULL,
    UNIQUE(source_id, version, checksum)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES knowledge_documents(document_id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    created_at_ms INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    content,
    tokenize='unicode61'
);

CREATE TABLE IF NOT EXISTS knowledge_nodes (
    node_id TEXT PRIMARY KEY,
    entity_key TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    aliases_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PROPOSED', 'CONFIRMED')),
    created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    edge_id TEXT PRIMARY KEY,
    source_node_id TEXT NOT NULL REFERENCES knowledge_nodes(node_id),
    target_node_id TEXT NOT NULL REFERENCES knowledge_nodes(node_id),
    relation_type TEXT NOT NULL,
    evidence_chunk_id TEXT NOT NULL REFERENCES knowledge_chunks(chunk_id),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status TEXT NOT NULL CHECK (status IN ('PROPOSED', 'CONFIRMED')),
    created_at_ms INTEGER NOT NULL,
    UNIQUE(source_node_id, target_node_id, relation_type, evidence_chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_kg_edge_source ON knowledge_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edge_target ON knowledge_edges(target_node_id);

CREATE TABLE IF NOT EXISTS rag_queries (
    query_id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    retrieval_config_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_evidence (
    query_id TEXT NOT NULL REFERENCES rag_queries(query_id) ON DELETE CASCADE,
    rank_no INTEGER NOT NULL,
    chunk_id TEXT NOT NULL REFERENCES knowledge_chunks(chunk_id),
    fused_score REAL NOT NULL,
    retrieval_channels_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    PRIMARY KEY(query_id, rank_no)
);

CREATE TABLE IF NOT EXISTS advisory_proposals (
    proposal_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    telemetry_frame_id TEXT REFERENCES telemetry_frames(telemetry_frame_id),
    rag_query_id TEXT REFERENCES rag_queries(query_id),
    proposal TEXT NOT NULL,
    risk_class TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    requires_human_confirmation INTEGER NOT NULL CHECK (requires_human_confirmation IN (0, 1)),
    issued_at_ms INTEGER NOT NULL,
    expires_at_ms INTEGER NOT NULL,
    gate_status TEXT NOT NULL CHECK (gate_status IN ('PASS', 'REJECT')),
    gate_reasons_json TEXT NOT NULL,
    model_version TEXT NOT NULL,
    schema_version TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_advisory_request_time
    ON advisory_proposals(request_id, issued_at_ms);
