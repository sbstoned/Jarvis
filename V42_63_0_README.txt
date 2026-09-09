Jarvis V42.63.0 - complete updated source and bundled assets

Fix for "AUTO routing could not activate either 27b38q2 or 9b35"

V42.61's PowerShell helper started llama-server and immediately exited with
code 0. The model manager treated that wrapper exit as a failed model load when
the native server had not finished initializing. AUTO could then kill that
still-loading model to try its peer and repeat the same premature failure.

Both launch paths now use one Python startup controller. It keeps the actual
llama-server process handle, waits through HTTP 503/loading, and verifies HTTP
health, the selected model and the live context before reporting success.
PowerShell exits successfully only after that verification. The native process
stays running for Jarvis. Startup is serialized across Windows launchers.

Model choice and speed

- AUTO HYBRID retains the Qwen3.5 9B worker and Qwen3.8 27B Aggressive Q2_K_P
  specialist. Routine code/test emission uses 9B; architecture and hard root-cause
  work can use 27B. Only one model is resident at a time.
- Every explicit model dropdown choice is a strict lock for the project. A
  manual 9B, 27B Q2, legacy 27B or 8B selection never falls back to another model.
- AUTO reuses a healthy pool member at project startup or starts the worker.
  Stage routing can promote later, avoiding an unnecessary initial 27B load.
- A model that exhausts startup recovery is skipped for the rest of that project
  while AUTO uses its available peer. A new request resets that startup history.
- Existing fast-routing, thinking, output and working-context controls remain.
  In particular, JARVIS_V4219_FAST_ROUTING and the JARVIS_QWEN35_WORKING_CONTEXT_*
  / JARVIS_QWEN38_WORKING_CONTEXT_* overrides retain their role. These changes
  do not introduce a time limit on an actively streaming repair response.
- The 9B now starts with a 40,960-token context, as the 27B already did. The
  262,144-token native capability remains available through explicit context
  overrides; it is not allocated just because the model supports it.

Memory recovery and diagnostics

The actual cause on a particular machine may also involve VRAM, RAM, the GGUF,
or the installed llama.cpp build. No host logs accompanied the reported failure.
The startup timing bug is present in the supplied code; memory exhaustion on
the user's machine was not independently measured.

- Only an actual allocation/out-of-memory error triggers memory recovery.
  There are at most three launches within the startup timeout, using the SAME
  selected GGUF: requested settings; a smaller context (normally 16,384 tokens);
  then the smaller context with at most 16 GPU layers. Duplicate settings are
  skipped. Reduced GPU offload may run slower if it is needed to fit the model.
- JARVIS_QWEN_GPU_LAYERS can set all, auto or a nonnegative layer count. Fallback
  never raises an explicit numeric count. JARVIS_QWEN_STARTUP_FALLBACK=0 disables
  the recovery ladder. Existing CACHE_TYPE_K/V overrides are retained.
- JARVIS_QWEN_35_CONTEXT / JARVIS_QWEN_35_9B_CONTEXT control 9B context.
  JARVIS_QWEN_38_RUNTIME_CONTEXT / JARVIS_QWEN_38_CONTEXT control the 27B Q2 context.
  Prompt/output budgets honor the live slot and its recorded fallback.
- Startup Stop, failure and timeout terminate and reap the owned native process.
  Logs go directly to files, avoiding a filled stdout/stderr pipe.
- qwen_startup_report.json records the latest startup attempt. Separate
  qwen_startup_report_9b35.json and qwen_startup_report_27b38q2.json retain each
  AUTO member's last attempts even after a switch. They include native exit codes,
  commands, settings and bounded log excerpts. The native logs remain
  qwen_server_stdout.log and qwen_server_stderr.log.
- Missing executables/models, unsupported model architectures, occupied ports
  and context mismatches now produce specific errors. Such errors are not
  disguised as memory failures. JARVIS_QWEN_PORT and JARVIS_QWEN_BASE_URL must
  identify the same local HTTP server; provider defaults honor the chosen port.
- The UI's model-ready update reports the model actually activated, including
  AUTO fallback, rather than always displaying 27B.

Earlier repair fixes included

This complete bundle includes V42.62's shared volatile-cache exclusion across
all candidate/resume/checkpoint copy paths, candidate preflight, strict raw-file
retry after malformed new-test JSON, and bounded truncation recovery. It keeps
the compiler, workflow-test and functional acceptance gates. Contradictory tests
and failing candidate changes still cannot be promoted.

Updating V42.61 or V42.62

1. Stop/checkpoint active work and fully close Jarvis. Back up its current folder.
2. Extract this archive into a separate temporary folder.
3. Copy the relative paths listed in V42_63_0_CHANGED_FILES.txt into your existing
   Jarvis folder, replacing those versions. This is a cumulative list from V42.61.
   It deliberately leaves your latest projects, runtime memory and saved choices
   in place. Do not overwrite current runtime data with older bundled copies.
4. Relaunch using your existing START_COMMAND_CENTER.bat or normal launcher.
   That custom BAT was absent from the uploaded archive, so it is not replaced.
   START_QWEN_LOCAL.ps1 retains its original optional parameters and now waits
   for readiness. It uses your configured Jarvis Python environment.
5. Confirm V42.63.0 in the active engine. Choose AUTO HYBRID or the specific model
   you want, then retry the project or attach your latest resumable checkpoint.

No model weights, driver or llama.cpp executable are replaced. Their installed
paths and the existing model downloads remain supported. This is an engine
update; the GearTrack checkpoint was not supplied and its final React/Rust tests
still need a resumed validation run.

Verification

229 counted checks passed, plus the optional-parameter launcher compatibility
script: 173 unit/integration tests (including 29 new startup/routing checks),
17 functional promotion checks, 10 volatile-cache checks and 29 hybrid/dropdown
checks. The startup suite runs real child processes and local HTTP fixtures for
delayed readiness, memory failures, large stderr, wrong model/context, Stop,
timeout, cleanup and selection policy. Prior real Python/SQLite workflow and
strict transaction tests also passed. The validation report is included.

These checks ran on Linux/Python 3.12 with controlled server/model responses.
PowerShell parameter wiring was checked; Windows process/mutex execution, live
Qwen GPU loading and the user's React/Rust project were not run here. The changes
remove demonstrated engine blockers and retain generic repair behavior; they do
not guarantee every arbitrary application can be completed on every host.

To run the new offline checks in your configured installation:
  CHECK_V4263_MODEL_STARTUP.bat

llama.cpp protocol reference (health 503 while loading, 200 when ready; /props):
  https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
