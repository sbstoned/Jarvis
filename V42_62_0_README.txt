Jarvis V42.62.0 - complete updated source and bundled assets

What this fixes

The V42.61 resume/checkpoint exclusions did not cover the active disposable
candidate-validation clone. A live npm cache under .jarvis_shared_build_cache
could therefore abort validation after a long model generation.

- All 12 source-copy call sites now share one owned-cache exclusion policy.
  Root, nested and case-variant cache names are excluded before traversal.
  Caller-specific exclusions and runtime dependency projection are preserved.
- Functional transactions prepare the disposable workspace before requesting
  model output. One bounded filesystem retry does not consume a model call.
- Persistent source-copy failures remain explicit infrastructure failures.
  They retain the model repair budget, avoid a pointless specialist model audit,
  and allow the same checkpoint to resume after the filesystem problem is fixed.
- If a new test's JSON response is malformed, a retry can request one strictly
  framed source file instead. Paths, completion markers and scope remain strict;
  Jarvis does not salvage truncated JSON or accept partial code.
- Truncated responses can retry as a smaller complete transaction even when the
  output allowance is already at its hardware-fit cap. Retries remain bounded.
- New tests must satisfy the original behavior and pass the existing component
  proof before promotion. Failing assertions cannot be accepted as progress.
- A new strategy generation allows the corrected engine to reconsider repair
  groups exhausted under V42.61.

Updating an existing installation

1. Stop/checkpoint any active generation, then fully close Jarvis's dashboard
   and voice-engine processes. Back up your current Jarvis folder.
2. Extract this archive to a separate temporary folder.
3. Copy the files listed in V42_62_0_CHANGED_FILES.txt into your existing Jarvis
   folder, replacing their older versions. Every listed path is relative to the
   archive root. The list excludes runtime memory, saved projects and credentials.
   This archive also contains the complete original bundle, including its large
   voice and UI assets; those unchanged files need not be recopied for an update.
4. Relaunch with your existing START_COMMAND_CENTER.bat. That custom launcher was
   not present in the uploaded V42.61 archive, so this update does not replace it.
   The included OPEN_JARVIS_DASHBOARD.bat remains available for the dashboard.
5. Check that the active engine reports V42.62.0. Attach your latest project
   checkpoint and ask: "Finish this project from this checkpoint. Preserve its
   working features and complete the remaining workflow tests."

Do not start over merely to install this engine fix. The last two project issues
still require a new validation run; the project checkpoint itself was not supplied
with this request. The engine ZIP is not a completed GearTrack application.

Validation

171 focused checks passed: 137 transaction/protocol/workflow tests, 17 promotion
guards, 10 resume-cache checks and 7 hardware-fit context checks. Eighteen tests
are new for this release. The full validation report is included.

The tests reproduced a disappearing-cache copy failure, exercised the active
clone paths, drove controlled model responses through real local HTTP streaming,
and ran real Python builds/tests with SQLite persistence and process restart.
A deliberately contradictory generated test stayed rejected. These checks ran
on Linux with Python 3.12; the Windows error condition was injected. A live Qwen
model, Windows launcher, Rust compiler and the user's GearTrack checkpoint were
not run in this environment.

The repair changes are independent of application language/framework. Existing
registered toolchains and full-project acceptance gates remain in charge. This
fix removes demonstrated engine blockers; it does not guarantee successful
creation of every arbitrary application on every machine.

To rerun the new checks on your configured machine:
  CHECK_V4262_CANDIDATE_WORKFLOW_RECOVERY.bat
