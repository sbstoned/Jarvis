JARVIS V42.11 - ROBUST EXISTING-PROJECT ZIP RESUME IMPORT
=========================================================

V42.11 preserves the complete V42.10 autonomous-builder/convergence engine and fixes
existing-project ZIP resume/import failures on Windows.

ROOT CAUSE FIXED
----------------
Prior Jarvis project checkpoints can contain deep rebuildable paths such as:
  .jarvis_runtime/cache/...
  .jarvis_backups/...
  .jarvis_failures/model_outputs/<timestamp>_<flattened source path>.txt
  node_modules/...
  src-tauri/target/...

When these were extracted under a deep generated_projects/<resume>/working path, Windows
could exceed its traditional path limit. Python then surfaced FileNotFoundError/Errno 2
on an internal diagnostic mirror before Jarvis reached the actual project source.

V42.11 now:
- validates every ZIP member against path traversal;
- rejects/ignores ZIP symlinks rather than following them;
- rejects drive-absolute and UNC ZIP members;
- strips one redundant top-level project wrapper when the whole archive shares it;
- prunes rebuildable dependency/build/runtime/cache/checkpoint trees during resume import;
- skips optional malformed-model-output diagnostic mirrors;
- uses Windows extended-length paths as a fallback for legitimate authored files;
- preserves source, manifests, tests, assets, migrations, compact Jarvis state/ledgers;
- writes JARVIS_V4211_IMPORT_REPORT.json into the resumed working project;
- no longer packages .jarvis_runtime or .jarvis_failures into final/checkpoint project ZIPs.

The strict final build/test/runtime/zero-debt publication gate is unchanged.
AUTO remains Qwen3.5 9B + NEW Qwen3.8 27B Aggressive Q2_K_P specialist only.

RECOMMENDED USE
---------------
For an almost-complete previous project, attach that project ZIP to V42.11 and ask Jarvis
to finish it. V42.11 will import the authored project without restoring rebuildable caches,
then run the whole-project audit/convergence flow from V42.10.

Validation: 530/530 regression checks PASS.
Exact project_20260831_204118 checkpoint import replay: PASS.
