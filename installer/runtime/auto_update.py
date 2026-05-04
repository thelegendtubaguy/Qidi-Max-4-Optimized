from __future__ import annotations

import getpass
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from . import messages, safety
from .errors import ActivePrintError, InstallerError, PrinterStateError
from .fs_atomic import atomic_write_text
from .models import RuntimePaths
from .naming import BUNDLE_ROOT_NAME

DEFAULT_ARCHIVE_URL = "https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/tltg-optimized-macros.tar.gz"
DEFAULT_CHECKSUM_URL = f"{DEFAULT_ARCHIVE_URL}.sha256"
LOCK_HELD_ENV = "TLTG_OPTIMIZED_INSTALLER_LOCK_HELD"
STATE_FILE = "config/tltg_optimized_auto_update_state.json"
SERVICE_NAME = "tltg-optimized-auto-update.service"
TIMER_NAME = "tltg-optimized-auto-update.timer"
SYSTEMD_DIR = Path("/etc/systemd/system")
PUBLIC_DEFAULT_SUDO_PASSWORD = "qiditech"
SUDO_PASSWORD_ENV = "TLTG_OPTIMIZED_SUDO_PASSWORD"

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
        enable_auto_updates(
            paths=paths,
            reporter=reporter,
            input_stream=input_stream,
            environ=environ,
            urlopen=urlopen,
        )
    except AutoUpdateError as exc:
        reporter.line(f"{messages.AUTO_UPDATE_ENABLE_FAILED} {exc.message}")
        return False
    return True


def enable_auto_updates(
    *,
    paths: RuntimePaths,
    reporter,
    input_stream=None,
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
    sudo_password = _authenticate_sudo(
        run=run,
        environ=env,
        reporter=reporter,
        input_stream=input_stream,
    )
    _install_systemd_units(paths=paths, run=run, sudo_password=sudo_password)
    _run_sudo_or_raise(
        ["systemctl", "daemon-reload"],
        messages.AUTO_UPDATE_SYSTEMD_FAILED,
        run=run,
        password=sudo_password,
    )
    _run_sudo_or_raise(
        ["systemctl", "enable", "--now", TIMER_NAME],
        messages.AUTO_UPDATE_SYSTEMD_FAILED,
        run=run,
        password=sudo_password,
    )
    reporter.line(messages.AUTO_UPDATE_ENABLED)


def auto_updates_configured() -> bool:
    return (SYSTEMD_DIR / TIMER_NAME).exists() or (SYSTEMD_DIR / SERVICE_NAME).exists()


def disable_auto_updates(
    *,
    paths: RuntimePaths,
    reporter,
    input_stream=None,
    run: RunFn = subprocess.run,
    require_sudo: bool = True,
) -> None:
    if shutil.which("systemctl") is None:
        _remove_state(paths)
        reporter.line(messages.AUTO_UPDATE_DISABLED)
        return
    if require_sudo and shutil.which("sudo") is None:
        raise AutoUpdateError(messages.AUTO_UPDATE_SUDO_MISSING)

    env = os.environ
    if require_sudo:
        reporter.line(messages.AUTO_UPDATE_SUDO_PROMPT)
        sudo_password = _authenticate_sudo(
            run=run,
            environ=env,
            reporter=reporter,
            input_stream=input_stream,
        )
        _run_sudo_ignore_failure(
            ["systemctl", "disable", "--now", TIMER_NAME],
            run=run,
            password=sudo_password,
        )
        for unit in (SERVICE_NAME, TIMER_NAME):
            _run_sudo_ignore_failure(
                ["rm", "-f", str(SYSTEMD_DIR / unit)],
                run=run,
                password=sudo_password,
            )
        _run_sudo_ignore_failure(
            ["systemctl", "daemon-reload"],
            run=run,
            password=sudo_password,
        )
    else:
        _run_ignore_failure(["systemctl", "disable", "--now", TIMER_NAME], run=run)
        for unit in (SERVICE_NAME, TIMER_NAME):
            _run_ignore_failure(["rm", "-f", str(SYSTEMD_DIR / unit)], run=run)
        _run_ignore_failure(["systemctl", "daemon-reload"], run=run)
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
    _run_latest_installer(
        paths=paths,
        archive_url=_archive_url(env),
        expected_checksum=checksum,
        urlopen=urlopen,
        run=run,
        environ=env,
    )
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


def _install_systemd_units(*, paths: RuntimePaths, run: RunFn, sudo_password: str) -> None:
    tmp_root = Path(tempfile.mkdtemp(prefix="tltg-auto-update-units-"))
    try:
        service_path = tmp_root / SERVICE_NAME
        timer_path = tmp_root / TIMER_NAME
        service_path.write_text(service_text(paths), encoding="utf-8")
        timer_path.write_text(timer_text(), encoding="utf-8")
        _run_sudo_or_raise(
            ["install", "-m", "0644", str(service_path), str(SYSTEMD_DIR / SERVICE_NAME)],
            messages.AUTO_UPDATE_SYSTEMD_FAILED,
            run=run,
            password=sudo_password,
        )
        _run_sudo_or_raise(
            ["install", "-m", "0644", str(timer_path), str(SYSTEMD_DIR / TIMER_NAME)],
            messages.AUTO_UPDATE_SYSTEMD_FAILED,
            run=run,
            password=sudo_password,
        )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _run_latest_installer(
    *,
    paths: RuntimePaths,
    archive_url: str,
    expected_checksum: str,
    urlopen: UrlOpenFn,
    run: RunFn,
    environ: dict[str, str],
) -> None:
    if paths.bundle_root.name != BUNDLE_ROOT_NAME:
        raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED)

    tmp_root = Path(tempfile.mkdtemp(prefix="tltg-auto-update-"))
    archive_path = tmp_root / "bundle.tar.gz"
    extract_root = tmp_root / "extract"
    try:
        _download_archive(archive_url, archive_path, urlopen=urlopen)
        _verify_archive_checksum(archive_path, expected_checksum)
        _extract_validated_archive(archive_path, extract_root)
        staged_bundle = extract_root / BUNDLE_ROOT_NAME
        if not (staged_bundle / "install.sh").is_file():
            raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED)

        replacement = tmp_root / BUNDLE_ROOT_NAME
        shutil.move(str(staged_bundle), replacement)
        if paths.bundle_root.exists():
            shutil.rmtree(paths.bundle_root)
        shutil.move(str(replacement), paths.bundle_root)
        result = run(
            ["/bin/sh", str(paths.bundle_root / "install.sh"), "--yes", "--plain"],
            cwd=str(paths.bundle_root),
            text=True,
            env={**os.environ, **environ, LOCK_HELD_ENV: "1"},
        )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    if result.returncode != 0:
        raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED)


def _download_archive(archive_url: str, archive_path: Path, *, urlopen: UrlOpenFn) -> None:
    try:
        with urlopen(archive_url, timeout=60) as response:
            archive_path.write_bytes(response.read())
    except (OSError, urllib.error.URLError) as exc:
        raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FETCH_FAILED) from exc


def _verify_archive_checksum(archive_path: Path, expected_checksum: str) -> None:
    actual_checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if actual_checksum.lower() != expected_checksum.lower():
        raise AutoUpdateError(messages.AUTO_UPDATE_CHECKSUM_INVALID)


def _extract_validated_archive(archive_path: Path, extract_root: Path) -> None:
    extract_root.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            _validate_archive_members(members)
            archive.extractall(extract_root, members=members)
    except (tarfile.TarError, OSError) as exc:
        raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED) from exc


def _validate_archive_members(members: list[tarfile.TarInfo]) -> None:
    has_install_sh = False
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED)
        if not path.parts or path.parts[0] != BUNDLE_ROOT_NAME:
            raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED)
        if not (member.isfile() or member.isdir()):
            raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED)
        if member.name == f"{BUNDLE_ROOT_NAME}/install.sh" and member.isfile():
            has_install_sh = True
    if not has_install_sh:
        raise AutoUpdateError(messages.AUTO_UPDATE_INSTALLER_FAILED)


def _run_or_raise(command: list[str], message: str, *, run: RunFn) -> None:
    result = run(command)
    if result.returncode != 0:
        raise AutoUpdateError(message)


def _authenticate_sudo(
    *,
    run: RunFn,
    environ: dict[str, str],
    reporter,
    input_stream,
) -> str:
    password = _initial_sudo_password(environ)
    if _run_sudo(["-v"], run=run, password=password).returncode == 0:
        return password
    fallback = _prompt_sudo_password(reporter=reporter, input_stream=input_stream)
    if fallback is None:
        raise AutoUpdateError(messages.AUTO_UPDATE_SUDO_FAILED)
    if _run_sudo(["-v"], run=run, password=fallback).returncode != 0:
        raise AutoUpdateError(messages.AUTO_UPDATE_SUDO_FAILED)
    return fallback


def _run_sudo_or_raise(
    command: list[str],
    message: str,
    *,
    run: RunFn,
    password: str,
) -> None:
    result = _run_sudo(command, run=run, password=password)
    if result.returncode != 0:
        raise AutoUpdateError(message)


def _run_sudo(
    command: list[str],
    *,
    run: RunFn,
    password: str,
    **kwargs,
) -> subprocess.CompletedProcess:
    return run(_sudo_command(command), input=password + "\n", text=True, **kwargs)


def _run_ignore_failure(command: list[str], *, run: RunFn) -> None:
    run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _run_sudo_ignore_failure(
    command: list[str],
    *,
    run: RunFn,
    password: str,
) -> None:
    _run_sudo(
        command,
        run=run,
        password=password,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _sudo_command(command: list[str]) -> list[str]:
    return ["sudo", "-S", "-p", "", *command]


def _initial_sudo_password(environ: dict[str, str]) -> str:
    return environ.get(SUDO_PASSWORD_ENV, PUBLIC_DEFAULT_SUDO_PASSWORD)


def _prompt_sudo_password(*, reporter, input_stream) -> str | None:
    if input_stream is None:
        return None
    reporter.prepare_for_prompt()
    use_getpass = input_stream is sys.stdin and getattr(input_stream, "isatty", lambda: False)()
    if hasattr(reporter, "emit_prompt") and not use_getpass:
        reporter.emit_prompt(
            question=messages.AUTO_UPDATE_SUDO_INITIAL_FAILED,
            instruction=messages.AUTO_UPDATE_SUDO_PASSWORD_PROMPT,
        )
    else:
        reporter.line(messages.AUTO_UPDATE_SUDO_INITIAL_FAILED)
    if use_getpass:
        try:
            return getpass.getpass(
                messages.AUTO_UPDATE_SUDO_PASSWORD_PROMPT + " ",
                stream=reporter.stream,
            )
        except EOFError:
            return None
    if not hasattr(reporter, "emit_prompt"):
        reporter.line(messages.AUTO_UPDATE_SUDO_PASSWORD_PROMPT)
    response = input_stream.readline()
    if response == "":
        return None
    return response.rstrip("\n")


def _checksum_url(environ: dict[str, str]) -> str:
    return environ.get("TLTG_AUTO_UPDATE_CHECKSUM_URL") or environ.get(
        "TLTG_INSTALLER_CHECKSUM_URL", DEFAULT_CHECKSUM_URL
    )


def _archive_url(environ: dict[str, str]) -> str:
    return environ.get("TLTG_AUTO_UPDATE_ARCHIVE_URL") or environ.get(
        "TLTG_INSTALLER_ARCHIVE_URL", DEFAULT_ARCHIVE_URL
    )


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
    atomic_write_text(
        path,
        json.dumps({"latest_checksum": checksum}, sort_keys=True, indent=2) + "\n",
        mode=0o644,
    )


def _remove_state(paths: RuntimePaths) -> None:
    path = state_path(paths)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def state_path(paths: RuntimePaths) -> Path:
    return paths.printer_data_root / STATE_FILE
