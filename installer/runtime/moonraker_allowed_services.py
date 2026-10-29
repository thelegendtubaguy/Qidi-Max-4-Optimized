from __future__ import annotations

import re

from .errors import InstallerError


OPERATION = "moonraker_allowed_qidi_client"
FILE = "/home/qidi/printer_data/moonraker.asvc"
SERVICE = "qidi-client"
# Moonraker reads one unit name per line, with or without its ".service" suffix.
_SERVICE_NAME = re.compile(r"[A-Za-z0-9_.@-]+")


def patch_allowed_services(text: str) -> str:
    # Fluidd's service controls list only services Moonraker allows; QIDI's list omits the touchscreen app.
    names = [line.strip() for line in text.split("\n") if line.strip()]
    if not all(_SERVICE_NAME.fullmatch(name) for name in names):
        raise InstallerError("Moonraker allowed services list is not recognized; preserving it.")
    if SERVICE in names or f"{SERVICE}.service" in names:
        return text
    # QIDI ships the list without a final newline; the added line uses the file's own line endings.
    newline = "\r\n" if "\r\n" in text else "\n"
    separator = newline if text and not text.endswith("\n") else ""
    return text + separator + SERVICE + newline
