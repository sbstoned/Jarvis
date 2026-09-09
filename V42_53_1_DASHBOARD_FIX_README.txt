JARVIS V42.53.1 - Dashboard version check correction

WHY THE WARNING APPEARED
V42.53.0 updated the page and server build IDs but left a second, older v2.63
constant in the browser heartbeat check. Matching V42.53.0 files could therefore
display a false mismatch and fail to record a healthy dashboard connection.
Restarting alone could not correct that hardcoded comparison.

WHAT CHANGED
The heartbeat now uses the page's existing build identity. A real mismatch still
shows a warning, including the actual page and server versions. Health responses
must identify the Jarvis dashboard service. A recovered connection clears the
warning without reloading the page or interrupting a project. Upload, checkpoint,
repair, compilation and final-acceptance behavior from V42.53.0 is retained.

INSTALL AND USE
1. Let a real checkpoint save finish before closing Jarvis and its dashboard.
2. Back up your current Jarvis folder. Replace its application code with the
   files in this complete ZIP, keeping your existing Python environment, model
   files, credentials, personal settings, uploaded ZIPs and generated projects.
3. Start that updated copy using your normal main Jarvis launcher, then open or
   reload the dashboard. Both page and server should report the build
   v42.53.1-dashboard-identity. The project engine version is V42.53.1.
4. Attach your saved project ZIP and wait for Ready to repair before sending
   "Fix and finish this existing project."

IPC OFFLINE IS A SEPARATE STATUS
It means the dashboard's check could not reach the main Jarvis process. A valid
dashboard heartbeat does not establish that the core is running. Opening
OPEN_JARVIS_DASHBOARD.bat starts only the dashboard, not the main Jarvis process.
Use your normal main launcher and allow core startup to finish. If IPC remains
offline, inspect that launcher's console for a startup error. The main entry
currently checks its provider and calibrates the microphone before starting IPC.
An old saved agent card is not proof that the current core is connected.

The regression suite verifies that a real IPC refusal reports failure, retains
the uploaded ZIP byte-for-byte, and accepts the same ZIP after IPC reconnects.
Do not repeatedly submit repairs while the core is unavailable.

VALIDATION
Run CHECK_V4253_PROJECT_UPLOADS.bat using your installed Python environment and
Node 20 or newer. It includes the new heartbeat and offline-core regressions
and invokes the prior repair/persistence suites. See
V42_53_1_VALIDATION_REPORT.json for results from this release.

Testing here uses real local HTTP servers, files, IPC routing, source import,
SQLite persistence and the production JavaScript in a Node VM with a minimal
DOM. Expensive model launch is replaced by a test fixture. This does not certify
a Windows desktop session, live Qwen generation or every generated project.

The older V42_53_PROJECT_UPLOADS_README.txt and V42_53_VALIDATION_REPORT.json
document the preceding release; this file provides the current installation
instructions and supersedes their version numbers.
