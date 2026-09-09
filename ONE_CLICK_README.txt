JARVIS v2.8.2 - ONE-CLICK + FULLSCREEN

ONE-TIME SETUP
--------------
Double-click:
  INSTALL_DESKTOP_SHORTCUT.bat

This creates:
  JARVIS Command Center
on your Windows desktop.

NORMAL START
------------
After setup, just double-click the desktop shortcut.

You can also directly double-click:
  START_COMMAND_CENTER.bat

It automatically:
1. Restarts/starts Hermes gateway
2. Starts Jarvis voice engine
3. Starts dashboard.py
4. Waits for the dashboard API
5. Opens Chrome or Edge in app mode

APP MODE
--------
The dashboard launches without the normal browser URL/address bar.

TRUE FULLSCREEN
---------------
Click the "FULLSCREEN" button in the top-right HUD.
Click it again to exit.

Browser fallback:
  F11

FILES
-----
START_COMMAND_CENTER.bat
START_COMMAND_CENTER_KIOSK.bat
INSTALL_DESKTOP_SHORTCUT.bat
CREATE_DESKTOP_SHORTCUT.ps1

The launcher uses:
  .venv\Scripts\python.exe

It does NOT require running Activate.ps1, so the PowerShell publisher warning
does not affect normal one-click startup.
