Jarvis V42.12 — Attached ZIP Resume Trial Isolation

Purpose
-------
V42.12 fixes a Windows resume failure that occurred after a ZIP was imported successfully. Dependency restore recreated Jarvis runtime caches inside the live working directory, then resume trial cloning attempted to copy those actively-changing cache files into trial_01. npm cache files could disappear during shutil.copytree, causing WinError 3 before Qwen reached the whole-project audit.

Behavior
--------
- Uploaded project ZIPs are safely extracted with the V42.11 importer.
- Resume trial/checkpoint clones copy authored source, manifests, tests, assets, and compact project state.
- Runtime/dependency/build caches are never copied into trials: .jarvis_runtime, .jarvis_failures, node_modules, target, build, dist, language caches, etc.
- Candidate-validation and smoke-test clones use the same isolation policy.
- A transient Windows copy race gets one clean retry; persistent authored-source failures remain hard errors.
- Whole-project audit, continuous IDE diagnostics, AUTO 9B/new 27B routing, global convergence, and zero-debt final publication remain enabled.

Validation
----------
551/551 regression checks PASS.
24 top-level Python files compile with 0 errors.
3 JavaScript syntax checks PASS.
Actual GearTrack checkpoint import -> live runtime cache creation -> trial_01 clone replay PASS.
