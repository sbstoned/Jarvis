JARVIS V42.53.0 - Reliable project ZIP attachments

INSTALL AND USE
1. Let any STOP + CHECKPOINT operation finish, then fully close Jarvis and its
   dashboard. Do not replace files while the old Python processes are running.
2. Back up your Jarvis folder, then extract this release over its application
   files. Reuse your installed Python environment, model files and provider
   credentials. Keep your saved project ZIPs.
3. Start the updated copy with its normal launcher. The dashboard health build
   is v42.53-reliable-project-uploads and the project engine is V42.53.0.
4. Click the paperclip, select the finished ZIP saved from your trial_03 folder,
   and wait for the attachment to say Ready to repair.
5. Send: Fix and finish this existing project.

A raw project ZIP is supported. It does not need Jarvis checkpoint metadata.
You can ZIP trial_03 itself or its contents. Existing wrapper stripping and
rebuildable-folder filtering remain active. Keep authored source, assets,
manifests, migrations and tests. Large rebuildable dependency/build folders
make transfers needlessly slow, but they are not interpreted as application
requirements. Project content is not restricted to any particular language.

WHAT CHANGED
- Upload starts with a small metadata request so size/disk problems produce an
  explicit message before the file is transmitted. Default maximum: 4 GiB;
  JARVIS_CHAT_UPLOAD_MAX_BYTES continues to override it.
- The browser reads and sends 1 MiB chunks instead of passing a mutable Windows
  File object to one large fetch request. Memory use stays bounded.
- Each chunk has a saved offset. Lost responses are retried without duplicate
  bytes. Retry resumes from saved data, including after a dashboard restart
  while the selected file and upload ID remain available in the browser.
- Partial files cannot become attachments. ZIP structure and paths are checked
  before an atomic finalization. The safe project importer validates extracted
  source members and retains its existing cache/path/symlink policies.
- Upload progress and recoverable errors stay visible. Retry and Remove are
  available. Send/Enter cannot race ahead of a pending or failed attachment.
- The server rejects missing, changed or incomplete attachment references.
  It no longer silently drops a ZIP and starts a new project from the prompt.
- A plain request to repair this/saved/attached project without an attachment
  asks for the ZIP before any generation job is queued.
- A typed IPC acknowledgement distinguishes accepting a dashboard command from
  actually accepting the ZIP repair job. A busy/offline worker retains the ZIP
  and draft. A stopping project cannot overlap a new project before its
  checkpoint is finished.
- The legacy /api/upload endpoint remains available for older clients.

VERIFICATION
Run CHECK_V4253_PROJECT_UPLOADS.bat with Python and Node 20+ installed. The suite
includes real HTTP requests through the dashboard, actual IPC routing, ZIP
import, byte-for-byte persistence checks, interrupted/lost-response transfers,
restart recovery, JavaScript upload/send behavior and prior repair regressions.
The JavaScript UI test uses minimal DOM objects for rendering; it is not a
Windows Chrome test. The expensive Qwen job launch is controlled in tests.
See V42_53_VALIDATION_REPORT.json for results and host limitations.

Existing V42.52 functional progress, compiler protections, related-file repair
transactions and final acceptance gates are preserved. Uploading successfully
does not certify the attached project as finished; its native build, tests,
runtime and functional gates must still pass during repair.
