JARVIS V42.53.2 - Chat submission and stale project job recovery

THE FAILURE IN YOUR SCREENSHOT
Your Enter key sent the request successfully, but the core refused it because
Agent 63 was recorded as stopping. Startup recovery previously retired queued
and running jobs but left stopping jobs active forever. It also failed to write
the recovered statuses back to disk, so the dashboard could show old Agent 69
activity while the core refused requests because of Agent 63.

THE CORRECTION
- Startup retires queued, running and stopping records from the previous process
  as interrupted and saves the corrected history. Existing source, checkpoint
  ZIPs, paths and completed results are preserved.
- The project slot belongs to a real worker thread. Orphan records cannot block
  a new repair. A live worker still owns the slot until it finishes cleanup,
  including while saving a checkpoint. Simultaneous requests start one worker.
- Job snapshots and file replacement use the same lock so concurrent progress
  updates cannot overwrite a newer status with an older one.
- The dashboard reads job state from the main Jarvis core. If the core cannot
  be reached, saved active records are labeled unconfirmed rather than presented
  as live activity. The dashboard does not kill or reset core jobs.
- Enter and the arrow button share the same submission function. Chat handlers
  initialize independently of optional widgets, and bind only once. Resizing a
  panel no longer captures clicks on the input or send button near its edge.
- A visible status beside the input distinguishes sending, waiting, acceptance
  and rejection. The draft and uploaded ZIP clear when the core accepts the
  repair. If it declines or disconnects, they remain available to retry.

INSTALL
1. Keep your saved project ZIP and back up your Jarvis folder.
2. Close the main Jarvis process and its dashboard before replacing code. If a
   worker is genuinely still running, allow its checkpoint save to finish first.
3. Replace the application files from this complete ZIP, preserving your current
   Python environment, models, credentials, settings and generated projects.
4. Start the updated main Jarvis launcher, then open the dashboard. The build ID
   is v42.53.2-live-project-jobs and the project engine is V42.53.2.
   OPEN_JARVIS_DASHBOARD.bat starts only the dashboard, not the main core.
5. Attach the saved ZIP, wait for Ready to repair, type your request and press
   Enter or click the arrow. Old Agent 63/69 records no longer reserve the slot.

Keep the current upload attached after a genuine busy-worker rejection; send it
again when the running worker finishes. A new request never discards an active
worker's workspace or interrupts its checkpoint to free the slot.

VALIDATION
CHECK_V4253_PROJECT_UPLOADS.bat runs the upload/UI suite, the new job lifecycle
suite, and the existing repair/persistence suites. Python and Node 20+ are needed.
See V42_53_2_VALIDATION_REPORT.json for this release's results.

The tests reproduce the exact Agent 63 rejection in the previous code. Updated
tests exercise keyboard and button event handlers, actual local HTTP and IPC,
the production job scheduler/worker, source ZIP import, a SQLite success/failure
workflow and persistence after process restart. Expensive model operations are
fixtures and the browser DOM is minimal. Windows desktop startup and live Qwen
generation were not executed here; no universal project-completion guarantee is
claimed. The language/framework detection and final acceptance gates are kept.

This file supersedes the installation/version details in earlier release notes,
which remain in the complete archive for history.
