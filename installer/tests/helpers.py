from __future__ import annotations

import atexit
import json
import shutil
import tempfile
import threading
from subprocess import CompletedProcess
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
BASE_RUNTIME_FIXTURE = FIXTURES_ROOT / "runtime" / "base"
REPO_ROOT = Path(__file__).resolve().parents[2]
MOONRAKER_QUERY_URL = "http://moonraker.invalid/printer/objects/query?print_stats"
_TEMP_ROOTS: list[Path] = []
def homing_fixture_bytes(firmware: str) -> bytes:
    if firmware not in {"01.01.06.03", "01.01.06.04", "01.01.06.05"}:
        raise ValueError(f"Unsupported homing fixture firmware: {firmware}")
    if firmware == "01.01.06.05":
        return homing_sync_reset_fixture_bytes()
    value = (REPO_ROOT / "installer/klipper/qidi/homing.py").read_bytes()
    value = value.replace(b"G4 P100", b"G4 P200").replace(b"G4 P50", b"G4 P200")
    value = value.replace(
        b'self.toolhead.dwell(\r\n            .25 if rails[0].get_name() in ("stepper_x", "stepper_y")\r\n            else 1)',
        b"self.toolhead.dwell(1)",
    )
    if firmware == "01.01.06.03":
        value = value.replace(
            b"G4 P200\\nSET_HOMING_MODE STEPPER=y VALUE=2",
            b"G4 P200SET_HOMING_MODE STEPPER=y VALUE=2",
        )
    return value


def homing_sync_reset_fixture_bytes() -> bytes:
    return (
        FIXTURES_ROOT
        / "source-patches/01.01.06.04/homing-sync-reset.py"
    ).read_bytes()


def temp_path(prefix: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix=prefix))
    _TEMP_ROOTS.append(root)
    return root



def _cleanup_temp_roots() -> None:
    for root in reversed(_TEMP_ROOTS):
        shutil.rmtree(root, ignore_errors=True)



atexit.register(_cleanup_temp_roots)



def copy_base_runtime() -> Path:
    temp_root = temp_path("installer-runtime-")
    shutil.copytree(BASE_RUNTIME_FIXTURE / "config", temp_root / "config")
    shutil.copy2(BASE_RUNTIME_FIXTURE / "firmware_manifest.json", temp_root / "firmware_manifest.json")
    target = temp_root / "klipper/klippy/extras"
    target.mkdir(parents=True, exist_ok=True)
    (target / "homing.py").write_bytes(homing_fixture_bytes("01.01.06.03"))
    return temp_root



def build_env(printer_data_root: Path, *, moonraker_url: str) -> dict[str, str]:
    return {
        "TLTG_OPTIMIZED_PRINTER_DATA_ROOT": str(printer_data_root),
        "TLTG_OPTIMIZED_KLIPPER_ROOT": str(printer_data_root / "klipper"),
        "TLTG_OPTIMIZED_FIRMWARE_MANIFEST": str(printer_data_root / "firmware_manifest.json"),
        "TLTG_OPTIMIZED_MOONRAKER_URL": moonraker_url,
    }



def fake_system_root(*, include_moonraker_cache: bool = False) -> Path:
    root = temp_path("system-optimization-flow-")
    (root / "etc/resolvconf/resolv.conf.d").mkdir(parents=True)
    (root / "etc/resolv.conf").write_text("nameserver 114.114.114.114\n", encoding="utf-8")
    (root / "etc/resolvconf/resolv.conf.d/head").write_text("nameserver 8.8.8.8\n", encoding="utf-8")
    (root / "etc/resolvconf/resolv.conf.d/tail").write_text("", encoding="utf-8")
    (root / "etc/apt").mkdir(parents=True)
    (root / "etc/apt/sources.list").write_text("old apt\n", encoding="utf-8")
    unit = root / "lib/systemd/system/rockchip.service"
    unit.parent.mkdir(parents=True)
    unit.write_text("[Service]\nExecStart=/etc/init.d/rockchip.sh\n", encoding="utf-8")
    script = root / "etc/init.d/rockchip.sh"
    script.parent.mkdir(parents=True)
    script.write_text(
        "#!/bin/bash -e\n"
        "rk3308\n"
        "CHIPNAME=\"rk3208\"\n"
        "mount -o remount,sync /\n"
        "install_packages\n"
        "touch /usr/local/first_boot_flag\n",
        encoding="utf-8",
    )
    gif = root / "home/qidi/QIDI_Client/access/account/process.gif"
    gif.parent.mkdir(parents=True)
    gif.write_bytes(b"old")
    (root / "systemd").mkdir()
    for service in ("xl2tpd", "bluetooth", "algo_app.service"):
        (root / "systemd" / f"{service}.json").write_text(
            json.dumps({"exists": True, "service": service, "enabled": "enabled", "active": "active"}, sort_keys=True),
            encoding="utf-8",
        )
    if include_moonraker_cache:
        moonraker = root / "home/qidi/moonraker/moonraker/components/file_manager/file_manager.py"
        moonraker.parent.mkdir(parents=True)
        moonraker.write_text(
            "from __future__ import annotations\n" +
            (REPO_ROOT / "installer/tests/fixtures/moonraker_metadata_storage.py").read_text(),
            encoding="utf-8",
        )
    (root / "mounts").mkdir()
    (root / "mounts/root.options").write_text("rw,relatime,sync\n", encoding="utf-8")
    return root


def fake_host_run(root: Path):
    """Bounded command fixture for systemd and root-mount interactions."""
    def service_state(service: str) -> dict:
        path = root / "systemd" / f"{service}.json"
        if not path.exists():
            return {"exists": True, "service": service, "enabled": "enabled", "active": "active"}
        return json.loads(path.read_text(encoding="utf-8"))

    def write_service_state(service: str, state: dict) -> None:
        path = root / "systemd" / f"{service}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    def result(command, *, stdout="", returncode=0):
        return CompletedProcess(command, returncode, stdout=stdout)

    def run(command, **_kwargs):
        command = list(command)
        if command[:4] == ["sudo", "-S", "-p", ""]:
            command = command[4:]
        if command == ["-v"]:
            return result(command)
        if command[:2] == ["systemctl", "is-enabled"]:
            state = service_state(command[2])
            return result(command, stdout=f"{state['enabled']}\n")
        if command[:2] == ["systemctl", "is-active"]:
            state = service_state(command[2])
            return result(command, stdout=f"{state['active']}\n")
        if command[:2] == ["systemctl", "show"]:
            service = command[2]
            state = service_state(service)
            prop = next((item.split("=", 1)[1] for item in command if item.startswith("--property=")), "")
            if prop == "ExecStart":
                dropin = root / "etc/systemd/system/rockchip.service.d/override.conf"
                source = dropin if dropin.is_file() else root / "lib/systemd/system/rockchip.service"
                values = [line.split("=", 1)[1].strip() for line in source.read_text(encoding="utf-8").splitlines() if line.strip().startswith("ExecStart=")]
                return result(command, stdout=(values[-1] if values else "") + "\n")
            values = {"ActiveState": state.get("active", "unknown"), "SubState": state.get("sub", "dead"), "Result": state.get("result", "success"), "ExecMainStatus": str(state.get("exec_main_status", 0))}
            return result(command, stdout=values[prop] + "\n")
        if command[:1] == ["findmnt"]:
            return result(command, stdout=(root / "mounts/root.options").read_text(encoding="utf-8"))
        if command[:2] == ["systemctl", "disable"]:
            service = command[-1]
            state = service_state(service)
            state.update({"enabled": "disabled", "active": "inactive"})
            write_service_state(service, state)
            return result(command)
        if command[:2] == ["systemctl", "enable"]:
            service = command[-1]
            state = service_state(service)
            state["enabled"] = "enabled"
            write_service_state(service, state)
            return result(command)
        if command[:2] in (["systemctl", "start"], ["systemctl", "stop"]):
            service = command[-1]
            state = service_state(service)
            state["active"] = "active" if command[1] == "start" else "inactive"
            write_service_state(service, state)
            return result(command)
        if command[:2] == ["systemctl", "restart"]:
            return result(command)
        if command[:2] == ["systemctl", "daemon-reload"] or command[:2] == ["systemctl", "reset-failed"]:
            return result(command)
        if command[:1] == ["mount"]:
            options = command[command.index("-o") + 1].split(",")
            (root / "mounts/root.options").write_text(
                ",".join(item for item in options if item not in {"remount", "sync", "async"})
                + (",async" if "async" in options else ",sync" if "sync" in options else "")
                + "\n",
                encoding="utf-8",
            )
            return result(command)
        if command and command[0].startswith("/etc/init.d/"):
            return result(command)
        raise AssertionError(f"Unexpected host command: {command}")

    return run


def snapshot_tree(root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    if not root.exists():
        return snapshot
    for item in sorted(root.rglob("*")):
        if item.is_file():
            snapshot[item.relative_to(root).as_posix()] = item.read_bytes()
    return snapshot


class _JsonResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def moonraker_urlopen(
    state: str | None = "standby", *, raw_payload=None, saved_variables_path: Path | None = None
):
    payload = raw_payload
    if payload is None:
        payload = {"result": {"status": {"print_stats": {"state": state}}}}
    process = {"pid": 100}

    def saved_variables():
        if saved_variables_path is None or not saved_variables_path.exists():
            return {"box_count": 0, "enable_box": 0}
        from installer.runtime import klipper_cfg

        text = saved_variables_path.read_text(encoding="utf-8")
        section = klipper_cfg.resolve_unique_section(text, "Variables")
        values = {}
        for line in text.splitlines(keepends=True)[section.header_index + 1 : section.end_index]:
            parsed = klipper_cfg.parse_option_line(line)
            if parsed is not None:
                values[parsed.key] = parsed.value.strip().strip("'\"")
        return values

    def persist_script(request):
        if saved_variables_path is None:
            return
        import ast
        import re
        import shlex

        body = json.loads(request.data.decode("utf-8"))
        script = body["script"]
        match = re.fullmatch(r"SAVE_VARIABLE VARIABLE=([a-z0-9_]+) VALUE=(.+)", script)
        if match is None:
            raise AssertionError(f"Unexpected G-code: {script}")
        name, raw_value = match.groups()
        value = repr(ast.literal_eval(shlex.split(raw_value)[0]))
        text = saved_variables_path.read_text(encoding="utf-8")
        from installer.runtime import klipper_cfg

        try:
            text = klipper_cfg.set_option_value(text, "Variables", name, value)
        except klipper_cfg.TargetResolutionError as exc:
            if exc.reason != "missing":
                raise
            text += f"{name} = {value}\n"
        saved_variables_path.write_text(text, encoding="utf-8")

    def urlopen(request, timeout=0):
        url = getattr(request, "full_url", str(request))
        if "/printer/gcode/script" in url:
            persist_script(request)
            return _JsonResponse({"result": "ok"})
        if "printer/objects/query?save_variables" in url:
            return _JsonResponse({"result": {"status": {"save_variables": {"variables": saved_variables()}}}})
        if "/machine/services/restart" in url:
            process["pid"] += 1
            return _JsonResponse({"result": "ok"})
        if "/printer/info" in url:
            return _JsonResponse({"result": {"state": "ready", "process_id": process["pid"]}})
        return _JsonResponse(payload)

    return urlopen


@contextmanager
def moonraker_server(state: str | None = "standby", *, raw_payload=None):
    payload = raw_payload
    if payload is None:
        payload = {"result": {"status": {"print_stats": {"state": state}}}}

    process = {"pid": 100}

    class Handler(BaseHTTPRequestHandler):
        def _respond(self, body):
            raw = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path.endswith("/printer/info"):
                self._respond({"result": {"state": "ready", "process_id": process["pid"]}})
            else:
                self._respond(payload)

        def do_POST(self):
            if self.path.endswith("/machine/services/restart"):
                process["pid"] += 1
            self._respond({"result": "ok"})

        def log_message(self, fmt, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/printer/objects/query?print_stats"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
