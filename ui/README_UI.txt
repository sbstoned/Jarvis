JARVIS COMMAND CENTER v5.0

Launch dashboard:
  C:\Users\<USER>\Jarvis\START_DASHBOARD.bat

Launch Jarvis + dashboard:
  C:\Users\<USER>\Jarvis\START_ALL.bat

Dashboard URL:
  http://127.0.0.1:8080

Live integration:
- jarvis.py writes live_state.json with STANDBY/LISTENING/TRANSCRIBING/THINKING/SPEAKING.
- The dashboard polls that state every 250 ms and animates the central neural core.
- Typed commands are sent to the running Jarvis process over local IPC port 8765.
- Voice commands such as "show calculator", "open email", "show calendar", and "open Word" can trigger dashboard widgets/app launches.
- The follow-up capture now starts immediately when TTS finishes; the old post-speech cooldown was removed.

