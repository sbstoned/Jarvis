JARVIS v2.13 HARDWARE TEMPERATURES

CPU and RAM utilization do not require psutil in this build.
Jarvis reads CPU utilization from Windows GetSystemTimes and RAM usage from
Windows GlobalMemoryStatusEx.

Actual temperatures require a hardware sensor provider because Windows does not
have one universal reliable API for CPU/DIMM temperatures.

Jarvis checks automatically:
1. LibreHardwareMonitor WMI sensors (recommended)
2. OpenHardwareMonitor WMI sensors
3. Windows ACPI thermal-zone data as a CPU-only fallback

If the dashboard says TEMP N/A, Jarvis is intentionally not inventing a number.
For real CPU and DIMM/RAM temperature values, run LibreHardwareMonitor with WMI
sensor exposure enabled. Jarvis will detect the sensors automatically.
