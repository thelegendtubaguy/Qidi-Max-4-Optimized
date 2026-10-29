from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from . import fluidd_build
from .errors import InstallerError


# The Fluidd Printer screen card connects through nginx to a package-owned screen service.
UNIT_OPERATION = "remote_screen_unit"
SERVER_OPERATION = "remote_screen_server"
NGINX_OPERATION = "remote_screen_nginx"
UNIT = "tltg-remote-screen.service"
UNIT_FILE = f"/etc/systemd/system/{UNIT}"
SERVER_FILE = "/usr/local/lib/tltg_remote_screen.py"
# The site operation also serves the package Fluidd build in place of QIDI's bundle; the operation keeps its original ID.
NGINX_SITE = "/etc/nginx/sites-available/fluidd"
NGINX_QIDI_ROOT = f"\n    root {fluidd_build.QIDI_ROOT};\n"
NGINX_BUILD_ROOT = f"\n    root {fluidd_build.DESTINATION};\n"
SERVER_PAYLOAD = Path(__file__).resolve().parents[1] / "system/tltg_remote_screen.py"
# Package-created files start with a marker line so later package versions replace earlier ones.
SERVER_MARKER = "# tltg-optimized:remote-screen-server\n"
UNIT_MARKER = "# tltg-optimized:remote-screen-unit\n"

# Restarting the unit without the server, before install or after restore, is a clean no-op.
UNIT_CONTENT = UNIT_MARKER + f"""\
# Serves the touchscreen to the Fluidd Printer screen card. Installed by QIDI Max 4 Optimized.
[Unit]
Description=QIDI Max 4 Optimized printer screen for Fluidd
After=network.target
ConditionPathExists={SERVER_FILE}

[Service]
Type=simple
User=qidi
SupplementaryGroups=video input
ExecStart=/home/qidi/moonraker-env/bin/python3 {SERVER_FILE}
Restart=on-failure
RestartSec=10
Nice=10
CPUQuota=60%
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
"""

NGINX_START = "    # tltg-optimized:remote-screen\n"
NGINX_END = "    # /tltg-optimized:remote-screen\n"
# Moonraker authorizes each connection: trusted client addresses, or the card's one-shot token.
NGINX_BLOCK = NGINX_START + """\
    location /tltg-screen/ {
        set $tltg_screen_token $arg_token;
        auth_request /tltg-screen-auth;
        proxy_pass http://127.0.0.1:7130/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $http_host;
        proxy_buffering off;
        proxy_read_timeout 60s;
        access_log off;
    }

    location = /tltg-screen-auth {
        internal;
        proxy_pass http://apiserver/access/user?token=$tltg_screen_token;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header Upgrade "";
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
""" + NGINX_END
NGINX_ANCHOR = "\n    location /webcam/ {\n"
NGINX_PREVIOUS = re.compile(re.escape(NGINX_START.rstrip("\n")) + r"\r?\n.*?" + re.escape(NGINX_END.rstrip("\n")) + r"\r?\n", re.DOTALL)


@lru_cache(maxsize=1)
def server_source() -> str:
    try:
        source = SERVER_PAYLOAD.read_text(encoding="utf-8")
    except OSError as exc:
        raise InstallerError(f"Printer screen service is missing from the package: {exc}") from exc
    if not source.startswith(SERVER_MARKER):
        raise InstallerError("Printer screen service payload lacks its package marker.")
    compile(source, "tltg_remote_screen.py", "exec")
    return source


def _patch_created(current: str, desired: str, marker: str, name: str) -> str:
    if current == "" or current.startswith(marker):
        return desired
    raise InstallerError(f"Existing {name} is unrecognized and was preserved.")


def patch_server(current: str) -> str:
    return _patch_created(current, server_source(), SERVER_MARKER, SERVER_FILE)


def patch_unit(current: str) -> str:
    return _patch_created(current, UNIT_CONTENT, UNIT_MARKER, UNIT_FILE)


def serves_fluidd_build(text: str) -> bool:
    return any(NGINX_BUILD_ROOT.replace("\n", newline) in text for newline in ("\n", "\r\n"))


def patch_nginx_site(text: str) -> str:
    # The route goes before QIDI's first webcam location and reuses its Moonraker upstream and upgrade map.
    # QIDI ships the site with CRLF line endings; changes use the file's own.
    newline = "\r\n" if "\r\n" in text else "\n"
    qidi_root = NGINX_QIDI_ROOT.replace("\n", newline)
    build_root = NGINX_BUILD_ROOT.replace("\n", newline)
    if text.count(qidi_root) + text.count(build_root) != 1:
        raise InstallerError("Fluidd nginx site does not match the reviewed QIDI source; preserving it.")
    text = text.replace(qidi_root, build_root, 1)
    block = NGINX_BLOCK.replace("\n", newline)
    previous = NGINX_PREVIOUS.findall(text)
    if len(previous) == 1:
        return text.replace(previous[0], block, 1)
    anchor = NGINX_ANCHOR.replace("\n", newline)
    if (
        not previous
        and text.count(anchor) == 1
        and "/tltg-screen" not in text
        and "proxy_pass http://apiserver/websocket;" in text
        and "$connection_upgrade" in text
    ):
        return text.replace(anchor, newline + block + anchor, 1)
    raise InstallerError("Fluidd nginx site does not match the reviewed QIDI source; preserving it.")
