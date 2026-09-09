JARVIS V31.2 - QWEN3.5 DEFAULT + MODEL-SWITCH UI FIX
=====================================================

Changes:
- Qwen3.5-9B HauhauCS Aggressive is the startup/default local model.
- AUTO resolves to Qwen3.5 when installed, then 8B, then 27B.
- Packaged qwen_selected_profile.json is set to 9b35 and INSTALL_REPLACEMENTS copies it.
- START_QWEN_LOCAL.ps1 defaults to 9b35 and AUTO prefers 9b35.
- Dashboard uses a new localStorage key so an old saved qwen8b browser value cannot visually override the new default.
- qwen_model_manager watches live /health + /props while the PowerShell launcher runs and returns as soon as the requested/fallback runtime is verified. This prevents project agents from remaining at 1% model_switch after Qwen is already live.

Qwen3.5 context ladder remains:
  1,010,000 (YaRN x4) -> 524,288 (YaRN x2) -> 262,144 native -> 131,072 native.
No automatic 40,960 Qwen3.5 fallback. 40,960 remains only for Qwen3-8B.
