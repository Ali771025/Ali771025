# Production Gate after v0.6-dev

The production version is not a rename of the development package. It starts only after these gates pass:

1. A labeled validation split exists for the target camera and operating domain.
2. YOLO reports per-class recall, false-negative rate, mAP50-95 and confidence calibration.
3. End-to-end P50/P95/P99 latency is measured on the target Jetson under thermal steady state.
4. Tracking and calibrated depth provide relative motion, uncertainty and TTC; a 2D box is never treated as distance.
5. Database retention, backup, restore, encryption and role access are tested.
6. SQLite is replaced by PostgreSQL for the ground service; edge buffering remains local and bounded.
7. ROS 2/PX4 integration is SITL-only until authority, QoS, watchdog and fault-injection suites pass.
8. Production containers use pinned digests, non-root users, health checks, read-only filesystems and signed model artifacts.
9. RAG/LLM remains read-only advisory with schema, evidence, TTL, policy and human-confirmation gates.
10. A formal release report records code, model, dataset, calibration, database migration and policy checksums.
11. Every GStreamer profile passes caps negotiation, reconnect, EOS and decoder/encoder fault tests on its target host.
12. ByteTrack is evaluated for IDF1/HOTA, ID switches, fragmentation and recovery after occlusion on a labeled target-domain sequence.
13. PTP/PPS or a measured clock-offset strategy replaces same-host monotonic matching when camera and flight computer run on separate hosts.
14. Stream authentication, network segmentation and secret injection are configured outside committed pipeline files.
15. Target maps are independently surveyed, georeferenced and reprojected to an approved metric CRS.
16. Route validation includes terrain/structure data accuracy, geofence version, wind limits and aircraft-specific dynamics.
17. Alternate-route latency and memory P50/P95/P99 are measured on Jetson AGX 64GB at maximum approved map size.
18. The scenario catalog is expanded with PX4 SITL/HIL fault injection, replay logs and signed acceptance evidence.
19. No route is sent to PX4 until an independent supervisor validates map version, route TTL, state freshness and authority.
20. Temporal-guard thresholds are validated against PTP/PPS measurements for every physical sensor host.
21. Energy coefficients are calibrated from aircraft-specific bench and flight-test logs across payload and wind envelopes.
22. Dynamic-track position, velocity and covariance are calibrated before they can hard-block a route corridor.
23. Readiness dependencies and heartbeat limits are exercised with process kill, network partition and recovery tests.
24. Assurance reports, model hashes, map hashes, policies and approvals are signed and retained according to release policy.
