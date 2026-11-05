from __future__ import annotations

from .errors import InstallerError


# QIDI's Debian cpufrequtils service sets the ondemand governor at boot, which samples every 10 ms and raises the
# clock only above 95% load. Klipper's short bursts rarely reach that, so they run at 408-600 MHz and take about 60%
# longer than at full speed. With a 65 C chamber, full speed held the SoC about 1 C warmer, well under the 85 C trip
# where the kernel throttles the CPU whatever the governor.
OPERATION = "cpu_performance"
FILE = "/etc/default/cpufrequtils"
SERVICE = "cpufrequtils.service"
# Package-created files start with a marker line so later package versions replace earlier ones.
MARKER = "# tltg-optimized:cpu-performance\n"
CONTENT = MARKER + """\
# Runs the CPU at full speed. Installed by Valve Oil.
ENABLE="true"
GOVERNOR="performance"
MAX_SPEED="0"
MIN_SPEED="0"
"""


def patch_defaults(current: str) -> str:
    if current == "" or current.startswith(MARKER):
        return CONTENT
    raise InstallerError(f"Existing {FILE} is unrecognized and was preserved.")
