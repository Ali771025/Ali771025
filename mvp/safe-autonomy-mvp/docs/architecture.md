# Architecture Decision Record - v0.6-dev

## Scope

The first executable baseline is a software-in-the-loop safety kernel for a non-weapon research platform. It has no PX4 publisher and no actuator adapter.

The Developer persistence profile uses SQLite with WAL, foreign keys and ordered SQL migrations. The production ground service will use PostgreSQL behind the same repository boundary.

## Trust boundaries

| Component | Trusted input | Output | Failure behavior |
| --- | --- | --- | --- |
| World Model | typed timestamped sensor observations | immutable snapshot | stale flag / no snapshot |
| Planner | snapshot + numeric goal | candidate trajectory | explicit PlanningError |
| Safety Supervisor | snapshot + candidate trajectory | PASS/REJECT gate trace | fail closed |
| Mission Manager | allowlisted Intent | bounded state transition | HOLD |
| Telemetry synchronizer | GPS/IMU/baro/airspeed/range/battery | immutable telemetry frame | stale/quality flags |
| Hybrid RAG | versioned documents and confirmed graph | cited evidence | empty evidence / ABSTAIN |
| Transformer advisory | telemetry summary + cited evidence | typed Intent only | rejected / ignored |
| GStreamer camera | BGR frame + PTS + host monotonic clock | bounded latest-frame queue | drop oldest / stop stream |
| YOLO + ByteTrack | BGR frame + pinned local model | 2D boxes + persistent track IDs | no objects / degraded health |
| Multimodal synchronizer | frame clock + telemetry clock | matched observation + skew | MISSING / TOO_OLD |
| Wiring validator | versioned module/port graph | checksum + validation reasons | reject startup |
| Map ingest/analyzer | allowlisted uploaded map | metric occupancy/risk/elevation grid | invalid/degraded map |
| Multi-criteria A* | analyzed map + typed request | ranked 2.5D alternatives | explicit PlanningError |
| Flight-state analyzer | synchronized state + route | phase/findings/bounded action | HOLD/RETURN/LAND/ABORT advisory |
| Scenario engine | versioned fault injection | deterministic pass/fail report | failed scenario gate |
| Temporal guard | normalized monotonic timestamp + sequence | accepted/degraded/rejected observation | reject stale/future/regressing data |
| Dynamic risk overlay | immutable map + fresh metric tracks | immutable projected map | ignore stale tracks / preserve static constraints |
| Route revalidator | validated route + dynamic map + current position | continue/replan/hold proposal | HOLD on blocked corridor |
| Energy estimator | route + capacity + state of charge + wind | feasibility and reserve trace | FAIL when reserve is consumed |
| Health manager | versioned module heartbeats | readiness snapshot | NOT_READY on required dependency loss |
| Mission assurance | map + route + readiness + energy | content-addressed PASS/WARN/FAIL report | FAIL if any hard gate fails |
| Observability | bounded latency samples | P50/P95/P99 and SLO ratio | bounded memory / explicit empty snapshot |

## Decisions

1. Domain core is independent from ROS 2, PX4, YOLO and any specific database.
2. Time is passed explicitly so replay tests are deterministic.
3. Snapshots are immutable and carry a unique identifier; a trajectory is invalid against a different snapshot.
4. Obstacle inflation includes geometric radius, policy margin and one standard deviation of positional uncertainty.
5. Safety is a separate evaluator and cannot be bypassed by Mission Manager.
6. Unknown control authority, stale state, low energy or any failed gate results in REJECT.
7. LLM integration cannot create waypoints or access an actuator API.
8. YOLO output is persisted as Detection2D; it cannot become a metric obstacle until calibrated depth and uncertainty are available.
9. Every video run stores the source SHA-256, model version, status and error state.
10. Raw IMU is stored and quality-checked but is not integrated as a replacement for PX4 EKF.
11. RAG fuses lexical, dense and graph rankings; every graph edge points to an evidence chunk.
12. Retrieved documents are untrusted data and cannot alter the system prompt or tool permissions.
13. Advisory output uses a closed schema, allowlisted intents, evidence validation and a bounded TTL.
14. ROS 2 bridge subscribes only; it creates no vehicle command, setpoint or actuator publisher.
15. Camera capture uses a one-buffer appsink plus a two-frame drop-oldest application queue.
16. Camera/PX4 matching uses the same host monotonic clock; wall clock and PX4 timestamps are retained for audit, not cross-domain matching.
17. ByteTrack IDs are persisted as image-plane tracks only; they do not imply range, TTC or a physical obstacle.
18. Startup rejects wiring with unknown ports, contract mismatch, multiple input producers, forbidden PX4 command contracts or an advisory-to-actuator path.
19. Annotated streaming is a presentation output and has no control authority.
20. Uploaded maps are bounded by file/cell limits, checksummed and converted into a metric grid before planning.
21. Unknown map cells are blocked by default; geofence/restricted/obstacle layers are hard constraints.
22. Risk, elevation and turns affect A* cost but cannot make a hard-blocked cell traversable.
23. Alternative routes are produced by deterministic corridor penalties and minimum distinctness, never by the LLM.
24. Flight phase transitions are validated independently from reported mode.
25. Every scenario stores its injected input, expected result, actual result and pass/fail evidence.
26. Sequence, freshness, future-time and cross-source skew checks occur before telemetry fusion.
27. Dynamic perception can only create a bounded temporary risk overlay; it cannot mutate the surveyed source map.
28. Route revalidation samples every grid cell along each segment, not only sparse route vertices.
29. Replan proposals use cooldown/hysteresis and never publish a flight command.
30. Energy feasibility preserves a configurable battery reserve and records all coefficients and observed inputs.
31. Required module loss produces `NOT_READY`; optional advisory-module loss produces `DEGRADED`.
32. Assurance hashes exclude transport UUIDs and therefore describe input content reproducibly.
33. Runtime metrics use bounded buffers and must be measured again on the target Jetson under steady thermal load.

## Planned adapters

- `adapters/yolo_replay`: converts detections plus calibration/depth into typed obstacles.
- `ros2_bridge`: read-only PX4 telemetry normalization and persistence.
- `adapters/px4_sitl`: accepts only a trajectory that has a matching PASS decision and TTL.
- `hybrid_rag`: FTS5 + embedding + Knowledge Graph + RRF + optional Qwen reranker.
- `gstreamer_io`: appsink/appsrc pipelines for V4L2, RTSP and RTP/UDP.
- `realtime_vision`: YOLO + ByteTrack + overlay + persistence + clock matching.
- `map_ingestion`: GeoJSON/PGM and optional GeoTIFF to a typed grid.
- `mission_route_planner`: multi-criteria A* with ranked alternatives.
- `flight_state_analyzer`: phase, health and bounded recommendation.
- `scenario_engine`: versioned SIL fault-injection catalog.

## Exit criteria before ROS 2/PX4 SITL

- unit and scenario tests pass;
- replay dataset and calibration version are pinned;
- P50/P95/P99 latency and stale-rate are measured;
- fault cases include missing pose, out-of-order data, frozen timestamps, control authority conflict and process loss;
- every accepted candidate has a complete gate trace.
- camera profiles are negotiated on target hardware and dropped-frame/latency metrics are recorded;
- camera-to-telemetry skew remains within the configured limit under load.
- uploaded maps have a pinned CRS, checksum, resolution and validation report;
- route alternatives pass collision, clearance, dynamics and distinctness gates;
- every enabled scenario passes on Jetson AGX and in CI before SITL.
