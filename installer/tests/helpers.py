from __future__ import annotations

import json
import shutil
import tempfile
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
BASE_RUNTIME_FIXTURE = FIXTURES_ROOT / "runtime" / "base"
REPO_ROOT = Path(__file__).resolve().parents[2]



def copy_base_runtime() -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix="installer-runtime-"))
    shutil.copytree(BASE_RUNTIME_FIXTURE / "config", temp_root / "config")
    shutil.copy2(BASE_RUNTIME_FIXTURE / "firmware_manifest.json", temp_root / "firmware_manifest.json")
    return temp_root



def build_env(printer_data_root: Path, *, moonraker_url: str) -> dict[str, str]:
    return {
        "TLTG_OPTIMIZED_PRINTER_DATA_ROOT": str(printer_data_root),
        "TLTG_OPTIMIZED_FIRMWARE_MANIFEST": str(printer_data_root / "firmware_manifest.json"),
        "TLTG_OPTIMIZED_MOONRAKER_URL": moonraker_url,
    }



def snapshot_tree(root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    if not root.exists():
        return snapshot
    for item in sorted(root.rglob("*")):
        if item.is_file():
            snapshot[item.relative_to(root).as_posix()] = item.read_bytes()
    return snapshot


@contextmanager
def moonraker_server(state: str | None = "standby", *, raw_payload=None):
    payload = raw_payload
    if payload is None:
        payload = {"result": {"status": {"print_stats": {"state": state}}}}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
