Jarvis V42.59.1 startup compatibility hotfix

Fixes a V42.59.0 regression where START_QWEN_LOCAL.ps1 declared -ModelPath as a
mandatory PowerShell parameter. Existing one-click START_JARVIS.bat launchers that
invoke the Qwen helper without that argument would therefore stop at an interactive
"ModelPath:" prompt and never finish bringing up Jarvis.

V42.59.1 keeps the existing START_JARVIS.bat workflow unchanged. When ModelPath is
omitted, START_QWEN_LOCAL.ps1 now:
  1. reads qwen_selected_profile.json when present,
  2. resolves the selected model from environment overrides / known D:-drive paths,
  3. mirrors Jarvis AUTO standby behavior when no direct selection is saved,
  4. launches non-interactively,
  5. retains the V42.59 native 262,144-token Hauhau 27B context target and adaptive
     output behavior.

Explicit -ServerExe / -ModelPath calls from qwen_model_manager.py remain supported.
