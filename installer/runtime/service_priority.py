from __future__ import annotations

from collections.abc import Callable

from .errors import InstallerError


# QIDI runs Klipper, Moonraker, and the touchscreen app at the same CPU priority. Keeping a print alive comes first,
# so Klipper gets the CPU before Moonraker, and both before the touchscreen app.
KLIPPER_OPERATION = "klipper_priority"
MOONRAKER_OPERATION = "moonraker_priority"
QIDICLIENT_OPERATION = "qidiclient_priority"
SERVICES = {
    KLIPPER_OPERATION: "klipper.service",
    MOONRAKER_OPERATION: "moonraker.service",
    QIDICLIENT_OPERATION: "qidi-client.service",
}
NICE = {
    KLIPPER_OPERATION: -10,
    MOONRAKER_OPERATION: -5,
    QIDICLIENT_OPERATION: 5,
}
FILES = {operation: f"/etc/systemd/system/{service}.d/tltg-priority.conf" for operation, service in SERVICES.items()}
# Package-created files start with a marker line so later package versions replace earlier ones.
MARKER = "# tltg-optimized:priority\n"


def content(operation: str) -> str:
    return MARKER + f"""\
# Sets this service's CPU priority. Installed by Valve Oil.
[Service]
Nice={NICE[operation]}
"""


def patch_dropin(operation: str) -> Callable[[str], str]:
    def patch(current: str) -> str:
        if current == "" or current.startswith(MARKER):
            return content(operation)
        raise InstallerError(f"Existing {FILES[operation]} is unrecognized and was preserved.")
    return patch
