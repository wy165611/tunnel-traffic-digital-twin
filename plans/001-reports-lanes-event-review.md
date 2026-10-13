# Plan 001: 分析报告、分车道趋势与报警证据复核

## Status
- Status: DONE — 2026-10-02, independently verified and delivered.
- Priority: P1
- Effort: L
- Risk: MED
- Category: direction
- Depends on: none
- Planned at: temporary source snapshot commit `ce63b01`, 2026-10-02. The original directory has no Git repository; changes are implemented in a disposable Git worktree, reviewed, then copied back only after the user's explicit implementation authorization.

## Why this matters
用户已选择并要求完成报告 → 车道趋势 → 报警复核，同时要求自行测试。现有系统可分析、下载三个 CSV，但无法阅读历史报告、比较结果或核验报警证据。交付应包括真实使用入口、中文说明、后端回归、前端构建和浏览器验收。

## Current state and conventions
- Python/FastAPI backend, React 19/TypeScript/Vite/ECharts frontend, native CSS and lucide icons; do not install dependencies or change the stack.
- `backend/exporter.py:10`: three CSV kinds (vehicles, traffic_statistics, events). CSVExporter uses an RLock for writes and snapshots; atomic_json writes metadata via temporary file replacement. Preserve compatibility and formula-safe CSV strings.
- `backend/service.py:109`: run.json has video_id, video_identity, segment_start, calibrated, config, scene, calibration. Runs are immutable historical analysis records except recording progress and new separate human-review records. No manufactured metadata for legacy runs.
- `backend/processor.py:36`: event_log deque(maxlen=500), history deque(maxlen=600); step exports world coordinates/speeds only with measured calibration and uses observed samples for counting and rules.
- `backend/traffic/traffic_metrics.py:11`: current per-lane count, cumulative flow and average speed already exist. New feature must be time-window trends rather than duplicating the existing dashboard.
- `frontend/src/components/EventPanel.tsx:4`: event rows have timestamp, vehicle_id and type but no actions.
- `backend/service.py:135`: seek closes the processor and clears analysis; evidence review MUST NOT use /control seek or rerun detection.
- `frontend/src/components/DataExportPanel.tsx:22`: paginated historical CSV downloads exist. Add report entry points here, with support for legacy runs.
- `frontend/src/components/ImportDialog.tsx` demonstrates Escape, focus trap, focus restoration, background scroll lock. New dialog may reuse it if title accessibility is parameterized compatibly, or match its behavior.
- README: actual video is bridge aerial footage, not validated tunnel footage. No real speed or speed-based alerts without measured scale. No API-dependent AI, no model training, no synthetic values disguised as real observations.

## Commands
From the isolated implementation directory:
- `TWIN_DATA_DIR=/tmp/twin-feature-tests .venv/bin/python -m pytest -q` → all tests pass, test exports isolated.
- `npm --prefix frontend test` → all tests pass.
- `npm --prefix frontend run build` → TypeScript and Vite succeed.
- `.venv/bin/python scripts/check_runtime.py` → HTTP, WS and graceful shutdown PASS.
- Use existing original models and videos via links in an isolated TWIN_DATA_DIR for real-video validation. Never write into original runs/calibrations during testing.

## Scope
In scope: backend/main.py, backend/exporter.py, backend/processor.py, backend/service.py (only metadata/evidence integration as needed), backend/traffic/flow_counter.py and new backend modules for reports, lane windows and evidence; new backend test files and minimal adjustments to existing tests/fixtures; frontend/src/App.tsx, frontend/src/types/index.ts, frontend/src/components/DataExportPanel.tsx, EventPanel.tsx, ImportDialog.tsx (compatible accessibility options only), new report/lane/evidence components and supporting utilities, frontend/src/styles.css, new frontend tests; README.md, CHANGELOG.md, docs/features-analysis.md. Match existing modules and atomic persistence/error conventions.
Out of scope: detection/tracking algorithms, measurement assumptions, original videos, weights, existing stored runs/calibrations, dependency versions, RTSP, multi-user auth, model training, automatic truth generation, live control actions in evidence view.
Do not commit, merge or push in the user's directory. No dependency installation. Do not copy changes back until reviewer authorization; report complete changed-file list.

## Ordered steps
### 1. Reports and comparable historical results
Implement a structured report reader/API for a validated run id and safe HTML printable report generated from consistent snapshots of saved CSVs and run.json. Use real analyzed time range, actual cumulative crossings, event counts by type, observed speed coverage (speed min/max/mean explicitly defined), metadata/source, calibration status, model/settings and downsampled time trends. Missing/empty files and unknown legacy metadata need honest null/unavailable states. CSV field escaping must not corrupt human-readable lane names. Printable report must escape all user data; no HTML interpolation vulnerabilities.
Add current/history report buttons and an in-app readable report dialog with a selectable comparison run; compare only same content hash, same start/end analyzed interval within explicit tolerance, same counting-line/lanes/calibration before suggesting differences are comparable; permit model/threshold differences but show them. Metadata missing or incompatible reports must show reasons and must not present a misleading superiority/accuracy conclusion. Avoid multiplying cumulative counts across frames; clearly name time-averaged or sample-averaged quantities. Snapshot active exporter files under its lock; bounded downsampling and streaming aggregation for long recordings.
Verify: new report tests for known CSV totals, uncalibrated nulls, empty/legacy runs, active-run read, illegal run id and mismatched comparisons. Backend suite, frontend test/build pass.

### 2. Persistent lane windows and trends
Support 10/30/60-second windows using actual video timestamps, not wall time. Capture crossing timestamp/lane accurately (extend FlowCounter without breaking existing metrics); compute window crossing count, actual covered duration and complete-window status. Short windows must be marked incomplete; do not label extrapolated rates as measured full-minute flows. Count/speed trends should distinguish observed samples from tracker predictions. Add bounded live lane_history to snapshots and a lane_statistics CSV with clear columns, preserving three existing CSVs and extending allowed export kinds. Provide historical lane trends in report as well as a responsive live lane trend panel with window selector and readable table/chart. Unassigned lane handled explicitly; empty scenes have useful draw-lane guidance. Speed null remains null when uncalibrated. No road area/time occupancy metric in this first stage unless rigorously defined and tested; leave existing unavailable label honest.
Verify: boundaries at exactly t-window, irregular timestamps, segment offset, empty/no lanes, observed vs predicted, short windows, reset and old CSV compatibility; rendered selector changes displayed data and CSV downloads correspond to saved records.

### 3. Persist evidence BEFORE adding independent review/replay
Give each new event a stable event_id and run_id. At trigger atomically persist a screenshot (annotated target box on actual resized frame) plus timestamp/frame, original/display dimensions, vehicle data and actually observed trajectory, rule config and calibrated state under the run directory. Evidence must remain attributable after video switch/restart. Immutable machine event/evidence vs separate mutable human review JSON: pending/confirmed/false_positive plus optional bounded note, persisted atomically and guarded against invalid ids/paths/statuses. Original CSV events still compatible; may append event_id field.
Provide event list/detail, screenshot endpoints and standalone original-video playback for the run's source, starting ~5 seconds before trigger and pausing ~5 seconds after; original video route must serve only the recorded valid video_id inside videos, and verify saved content identity before allowing it. If original source absent/mismatched, screenshot/metadata remain usable and playback clearly unavailable. Preserve snapshot overlays separately from raw original video; no claim that original replay includes detection overlays. HTTP Range support comes from FileResponse; avoid transcoding whole recordings or extra dependencies. Returning run-id/source metadata can update legacy states as unavailable, never fabricate evidence for old events.
Current event rows and historical report events open accessible review dialog: screenshot, rule facts, raw source video/timestamp, independent replay, review status/note/save, errors, Escape/focus restore. Opening it must not change the live session's video, run_id, status or counters. Human review does not suppress raw event counts; report distinguishes machine detections from human review counts.
Verify: calibrated synthetic trajectory triggers real detector rule and produces actual screenshot; uncalibrated sequence produces no speed alerts/evidence; review save/reload after new service instance; invalid/traversal ids; source missing/changed; live state unchanged across every read/review endpoint; responsive layout and keyboard behavior.

## Test plan and done criteria
Use tests/test_api.py's temporary videos and deterministic detector pattern; use existing frontend node:test/esbuild patterns for meaningful derived-data and stale-load behavior. Tests must cover report math, event identity, persisted reviews, source safety, counting semantics, incomplete time windows and null measurements. Preserve existing tests rather than weaken them.
All backend/frontend suites and production build pass. Reviewer independently executes real-video uncalibrated end-to-end and calibrated controlled-event end-to-end plus actual browser flows (report, comparison, windows, evidence, review persistence, empty/legacy states, 390px and 320px without document overflow). Document measured results without pretending synthetic tests establish real-world accuracy.

## STOP and maintenance
Report blocked paths/dependency/runtime issues instead of installing global tools or changing original data. If source identity cannot be verified, disable original playback. If report files are incomplete, return explicit unavailable state rather than invented zeros. New future CSV schemas must remain versioned/compatible and separate machine observations from human edits. Report full scope deviations to reviewer.

## Completion evidence

22 scoped source/test/doc files + 5 production files delivered after baseline drift and backup checks. Independent original-directory regression: 75 backend, 18 frontend; production build, HTTP/WS/shutdown, 14 API end-to-end checks and real browser flows PASS. See `plans/2026-10-02-feature-verification.md` and `plans/features-delivery-manifest.json`. No Git commit, merge or push. Original video/model/calibration/run data unchanged.
