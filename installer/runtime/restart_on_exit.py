from __future__ import annotations

from collections.abc import Callable

from .errors import InstallerError


# QIDI's Klipper and Moonraker units, from the upstream install scripts, set RemainAfterExit=yes. A process that exits
# cleanly outside systemd then stays down while its unit still reads active, so Restart=always never fires.
MOONRAKER_OPERATION = "moonraker_restart_on_exit"
KLIPPER_OPERATION = "klipper_restart_on_exit"
FILES = {
    MOONRAKER_OPERATION: "/etc/systemd/system/moonraker.service.d/tltg-restart-on-exit.conf",
    KLIPPER_OPERATION: "/etc/systemd/system/klipper.service.d/tltg-restart-on-exit.conf",
}
# Package-created files start with a marker line so later package versions replace earlier ones.
MARKER = "# tltg-optimized:restart-on-exit\n"
CONTENT = MARKER + """\
# Restarts the service after any exit outside systemd. Installed by QIDI Max 4 Optimized.
[Service]
RemainAfterExit=no
"""


def patch_dropin(path: str) -> Callable[[str], str]:
    def patch(current: str) -> str:
        if current == "" or current.startswith(MARKER):
            return CONTENT
        raise InstallerError(f"Existing {path} is unrecognized and was preserved.")
    return patch
