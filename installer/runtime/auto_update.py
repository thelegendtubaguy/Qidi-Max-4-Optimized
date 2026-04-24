from __future__ import annotations

import json
import os
import pwd
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import messages, safety
from .errors import ActivePrintError, InstallerError, PrinterStateError
from .models import RuntimePaths

DEFAULT_INSTALL_LATEST_URL = "https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/install-latest.sh"
DEFAULT_ARCHIVE_URL = "https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/tltg-optimized-macros.tar.gz"
DEFAULT_CHECKSUM_URL = f"{DEFAULT_ARCHIVE_URL}.sha256"
STATE_FILE = "config/tltg_optimized_auto_update_state.json"
SERVICE_NAME = "tltg-optimized-auto-update.service"
TIMER_NAME = "tltg-optimized-auto-update.timer"
SYSTEMD_DIR = Path("/etc/systemd/system")

UrlOpenFn = Callable[..., object]
RunFn = Callable[..., subprocess.CompletedProcess]


class AutoUpdateError(InstallerError):
    pass


@dataclass(frozen=True)
class AutoUpdateRunResult:
    action: str
    checksum: str | None = None


def maybe_prompt_enable_auto_updates(
    *,
    paths: RuntimePaths,
    reporter,
    input_stream,
    environ: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    from .interaction import confirm_yes

    if input_stream is None:
        return False
    if not confirm_yes(
        reporter=reporter,
        input_stream=input_stream,
        question=messages.AUTO_UPDATE_PROMPT,
        instruction=messages.AUTO_UPDATE_PROMPT_INSTRUCTION,
        cancel_message=messages.AUTO_UPDATE_NOT_ENABLED,
    ):
        return False
    try:
        enable_auto_updates(paths=paths, reporter=reporter, environ=environ, urlopen=urlopen)
    except AutoUpdateError as exc:
        reporter.line(f"{messages.AUTO_UPDATE_ENABLE_FAILED} {exc.message}")
        return False
    return True


def enable_auto_updates(
    *,
    paths: RuntimePaths,
    reporter,
    environ: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
    run: RunFn = subprocess.run,
) -> None:
    if shutil.which("systemctl") is None:
        raise AutoUpdateError(messages.AUTO_UPDATE_SYSTEMD_MISSING)
    if shutil.which("sudo") is None:
        raise AutoUpdateError(messages.AUTO_UPDATE_SUDO_MISSING)

    env = os.environ if environ is None else environ
    try:
        checksum = fetch_latest_checksum(_checksum_url(env), urlopen=urlopen)
    except AutoUpdateError:
        reporter.line(messages.AUTO_UPDATE_SEED_SKIPPED)
    else:
        _write_state(paths, checksum)

    reporter.line(messages.AUTO_UPDATE_SUDO_PROMPT)
    _run_or_raise(["sudo", "-v"], messages.AUTO_UPDATE_SUDO_FAILED, run=run)
    _install_systemd_units(paths=paths, run=run)
    _run_or_raise(["sudo", "systemctl", "daemon-reload"], messages.AUTO_UPDATE_SYSTEMD_FAILED, run=run)
    _run_or_raise(
        ["sudo", "systemctl", "enable", "--now", TIMER_NAME],
        messages.AUTO_UPDATE_SYSTEMD_FAILED,
        run=run,
    )
    reporter.line(messages.AUTO_UPDATE_ENABLED)


def auto_updates_configured() -> bool:
    return (SYSTEMD_DIR / TIMER_NAME).exists() or (SYSTEMD_DIR / SERVICE_NAME).exists()


def disable_auto_updates(
    *,
    paths: RuntimePaths,
    reporter,
    run: RunFn = subprocess.run,
    require_sudo: bool = True,
) -> None:
    if shutil.which("systemctl") is None:
        _remove_state(paths)
        reporter.line(messages.AUTO_UPDATE_DISABLED)
        return
    if require_sudo and shutil.which("sudo") is None:
        raise AutoUpdateError(messages.AUTO_UPDATE_SUDO_MISSING)

    command_prefix = ["sudo"] if require_sudo else []
    if require_sudo:
        reporter.line(messages.AUTO_UPDATE_SUDO_PROMPT)
        _run_or_raise(["sudo", "-v"], messages.AUTO_UPDATE_SUDO_FAILED, run=run)

    _run_ignore_failure(command_prefix + ["systemctl", "disable", "--now", TIMER_NAME], run=run)
    for unit in (SERVICE_NAME, TIMER_NAME):
        _run_ignore_failure(command_prefix + ["rm", "-f", str(SYSTEMD_DIR / unit)], run=run)
    _run_ignore_failure(command_prefix + ["systemctl", "daemon-reload"], run=run)
    _remove_state(paths)
    reporter.line(messages.AUTO_UPDATE_DISABLED)


def run_auto_update_check(
    *,
    paths: RuntimePaths,
    reporter,
    environ: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
    run: RunFn = subprocess.run,
) -> AutoUpdateRunResult:
    env = os.environ if environ is None else environ
    try:
        checksum = fetch_latest_checksum(_checksum_url(env), urlopen=urlopen)
    except AutoUpdateError:
        reporter.line(messages.AUTO_UPDATE_SKIPPED_CHECKSUM_UNAVAILABLE)
        return AutoUpdateRunResult(action="skipped-checksum-unavailable")
    state = _read_state(paths)
    if state.get("latest_checksum") == checksum:
        reporter.line(messages.AUTO_UPDATE_ALREADY_CURRENT)
        return AutoUpdateRunResult(action="already-current", checksum=checksum)

    try:
        safety.ensure_printer_idle(paths.moonraker_url, urlopen=urlopen)
    except ActivePrintError:
        reporter.line(messages.AUTO_UPDATE_SKIPPED_ACTIVE_PRINT)
        return AutoUpdateRunResult(action="skipped-active-print", checksum=checksum)
    except PrinterStateError:
        reporter.line(messages.AUTO_UPDATE_SKIPPED_UNKNOWN_STATE)
        return AutoUpdateRunResult(action="skipped-unknown-printer-state", checksum=checksum)

    if "latest_checksum" not in state:
        _write_state(paths, checksum)
        reporter.line(messages.AUTO_UPDATE_INITIALIZED)
        return AutoUpdateRunResult(action="initialized", checksum=checksum)

    reporter.line(messages.AUTO_UPDATE_AVAILABLE)
    _run_latest_installer(paths=paths, install_latest_url=_install_latest_url(env), urlopen=urlopen, run=run)
    _write_state(paths, checksum)
    reporter.line(messages.AUTO_UPDATE_COMPLETE)
    return AutoUpdateRunResult(action="updated", checksum=checksum)


def fetch_latest_checksum(
    checksum_url: str,
    *,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> str:
    try:
        with urlopen(checksum_url, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError, UnicodeDecodeError) as exc:
        raise AutoUpdateError(messages.AUTO_UPDATE_CHECKSUM_FETCH_FAILED) from exc
    first = body.strip().split()[0] if body.strip() else ""
    if len(first) != 64 or any(char not in "0123456789abcdefABCDEF" for char in first):
        raise AutoUpdateError(messages.AUTO_UPDATE_CHECKSUM_INVALID)
    return first.lower()


def service_text(paths: RuntimePaths) -> str:
    user = _current_user()
    return (
        "[Unit]\n"
        "Description=TLTG QIDI Max 4 optimized config auto-update\n"
        "Wants=network-online.target\n"
        "After=network-online.target\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"User={user}\n"
        f"WorkingDirectory={paths.bundle_root}\n"
        f"ExecStart={paths.bundle_root / 'auto-update.sh'} --run\n"
    )


def timer_text() -> str:
    return (
        "[Unit]\n"
        "Description=Run TLTG optimized config auto-update hourly\n\n"
        "[Timer]\n"
        "OnBootSec=10min\n"
        "OnUnitActiveSec=1h\n"
        "Persistent=true\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def _install_systemd_units(*, paths: RuntimePaths, run: RunFn) -> None:
    tmp_root = Path(tempfile.mkdtemp(prefix="tltg-auto-update-units-"))
    try:
        service_path = tmp_root / SERVICE_NAME
        timer_path = tmp_root / TIMER_NAME
        service_path.write_text(service_text(paths), encoding="utf-8")
        timer_path.write_text(timer_text(), encoding="utf-8")
        _run_or_raise(
            ["sudo", "install", "-m", "0644", str(service_path), str(SYSTEMD_DIR / SERVICE_NAME)],
            messages.AUTO_UPDATE_SYSTEMD_FAILED,
            run=run,
        )
        _run_or_raise(
            ["sudo", "install", "-m", "0644", str(timer_path), str(SYSTEMD_DIR / TIMER_NAME)],
            messages.AUTO_UPDATE_SYSTEMD_FAILED,
            run=run,
        )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _run_latest_installer(
    *,
    paths: RuntimePaths,
    install_latest_url: str,
    urlopen: UrlOpenFn,
    run: RunFn,
) -> None:
    try:
        with urlopen(install_latest_url, timeout=20) as response:
            script = response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FETCH_FAILED) from exc

    tmp_root = Path(tempfile.mkdtemp(prefix="tltg-auto-update-"))
    script_path = tmp_root / "install-latest.sh"
    try:
        script_path.write_bytes(script)
        script_path.chmod(0o700)
        result = run(
            ["/bin/sh", str(script_path), "--yes", "--plain"],
            cwd=str(paths.bundle_root.parent),
            text=True,
        )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    if result.returncode != 0:
        raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED)


def _run_or_raise(command: list[str], message: str, *, run: RunFn) -> None:
    result = run(command)
    if result.returncode != 0:
        raise AutoUpdateError(message)


def _run_ignore_failure(command: list[str], *, run: RunFn) -> None:
    run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _checksum_url(environ: dict[str, str]) -> str:
    return environ.get("TLTG_AUTO_UPDATE_CHECKSUM_URL") or environ.get(
        "TLTG_INSTALLER_CHECKSUM_URL", DEFAULT_CHECKSUM_URL
    )


def _install_latest_url(environ: dict[str, str]) -> str:
    return environ.get("TLTG_AUTO_UPDATE_INSTALL_LATEST_URL", DEFAULT_INSTALL_LATEST_URL)


def _current_user() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return os.environ.get("USER", "qidi")


def _read_state(paths: RuntimePaths) -> dict[str, str]:
    path = state_path(paths)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(paths: RuntimePaths, checksum: str) -> None:
    path = state_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"latest_checksum": checksum}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _remove_state(paths: RuntimePaths) -> None:
    path = state_path(paths)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def state_path(paths: RuntimePaths) -> Path:
    return paths.printer_data_root / STATE_FILE
