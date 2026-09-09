Jarvis V42.5 - Optional Qwen3.8-27B Aggressive Q2_K_P selector

Adds an explicit optional local model profile:
  Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf

Hugging Face repository:
  HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF

Behavior:
- Qwen3.5-9B remains the selected/default Jarvis local model.
- The Qwen3.8-27B Aggressive Q2_K_P entry appears directly below the 9B entry.
- The older 27B OBLITERATED profile remains available.
- Switching still uses one llama.cpp server / one resident local GGUF at a time.
- The new profile uses Qwen3.8-specific sampling defaults.
- Prompt budgeting reads the live llama.cpp context and uses a conservative 32K fallback for the larger model.

Default model path searched first:
  D:\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf

Override path with:
  JARVIS_QWEN_38_27B_AGGRESSIVE_Q2_MODEL_PATH

Optional downloader:
  DOWNLOAD_QWEN38_27B_AGGRESSIVE_Q2_K_P.bat
