from __future__ import annotations

from .errors import InstallerError


# QIDI's makerbase-webcam.service runs /root/auto-webcam-id.sh at boot to set the camera in crowsnest.conf. The script
# waits only until /dev/v4l/by-id/ has any link, then writes the camera's -video-index0 link, or nothing if it isn't
# there yet, over `device:`. udev can make the index1 link first: on the test printer index0 followed 260 ms later, the
# script wrote an empty device, and crowsnest stopped with "Parameter device not found", so Fluidd had no camera.
# The drop-in waits for an index0 link before the script runs, and skips the script if none appears within 30 s, so
# it never blanks the device; an empty device is filled in at the next boot.
OPERATION = "webcam_id_wait"
UNIT = "makerbase-webcam.service"
FILE = f"/etc/systemd/system/{UNIT}.d/tltg-wait-for-camera.conf"
# Package-created files start with a marker line so later package versions replace earlier ones.
MARKER = "# tltg-optimized:webcam-id-wait\n"
# systemd reads $$ as a literal $.
CONTENT = MARKER + """\
# Waits for the camera's index0 link before QIDI's auto-webcam-id.sh sets the crowsnest device. Installed by Valve Oil.
[Service]
ExecStartPre=/bin/sh -c 'i=0; while [ $$i -lt 60 ]; do for link in /dev/v4l/by-id/*-video-index0; do [ -e "$$link" ] && exit 0; done; i=$$((i + 1)); sleep 0.5; done; exit 1'
"""


def patch_dropin(current: str) -> str:
    if current == "" or current.startswith(MARKER):
        return CONTENT
    raise InstallerError(f"Existing {FILE} is unrecognized and was preserved.")
