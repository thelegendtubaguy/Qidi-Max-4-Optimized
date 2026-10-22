#!/usr/bin/env python3
"""Restricted Max 4 THR snapshots, bootloader probes, and confirmed transfers."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "firmware/max4-thr-lis2dw-fifo-v1.json"
if __package__:
    from . import thr_bootloaders
else:
    import thr_bootloaders

identify_bootloader = thr_bootloaders.identify_bootloader

DEVICE = "/dev/ttyS4"
UNSUPPORTED_BOOTLOADER = 3
SERVICES = ("klipper.service", "qidi-client.service", "tltg-optimized-auto-update.timer")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def admitted_image(data: bytes, manifest: dict) -> str:
    thr = manifest["thr"]
    value = digest(data)
    if len(data) != thr["size"] or value not in (thr["stock_sha256"], thr["patched_sha256"]):
        raise ValueError("Unrecognized THR image")
    return value


def load_backup(directory: Path, manifest: dict) -> tuple[bytes, bytes]:
    boot = (directory / "bootloader.bin").read_bytes()
    app = (directory / "application.bin").read_bytes()
    identify_bootloader(boot)
    admitted_image(app, manifest)
    return boot, app


def verify_readback(image: bytes, directory: Path, manifest: dict, *, expected_bootloader: bytes | None = None) -> dict:
    expected = admitted_image(image, manifest)
    boot, app = load_backup(directory, manifest)
    if expected_bootloader is not None and boot != expected_bootloader:
        raise ValueError("Bootloader readback differs from the original backup")
    if app != image:
        raise ValueError("Application readback does not match the selected image")
    return {"verified": True, "application_sha256": expected, "bootloader_sha256": digest(boot)}


def require_ownership(idle_confirmed: bool) -> None:
    if not idle_confirmed:
        raise ValueError("Confirm idle state and zero heater targets with --printer-idle-confirmed")
    for service in SERVICES:
        result = subprocess.run(
            ["systemctl", "show", service, "--property=ActiveState", "--value"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode and service == "tltg-optimized-auto-update.timer":
            load = subprocess.run(
                ["systemctl", "show", service, "--property=LoadState", "--value"],
                capture_output=True, text=True, timeout=5,
            )
            if load.stdout.strip() == "not-found":
                continue
        if result.returncode or result.stdout.strip() != "inactive":
            raise ValueError(f"Stop {service} before UART access")


def crc16(data: bytes) -> int:
    value = 0xffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return value ^ 0xffff


def encode(kind: int, payload: bytes) -> bytes:
    if kind not in (0, 1, 2) or len(payload) > 1030:
        raise ValueError("Invalid THR packet")
    body = bytes([kind]) + len(payload).to_bytes(2, "big") + payload
    return b"\xa5" + body + crc16(body).to_bytes(2, "big")


class RetryPacket(Exception):
    pass


class Bootloader:
    def __init__(self, port, profile, clock=time.monotonic):
        self.port = port
        self.profile = profile
        self.clock = clock
        self.buffer = bytearray()

    def receive(self, deadline: float):
        while self.clock() < deadline:
            while self.buffer:
                if self.buffer[0] != 0xa5:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < 4:
                    break
                size = int.from_bytes(self.buffer[2:4], "big")
                if size > 100:
                    del self.buffer[0]
                    continue
                end = size + 6
                if len(self.buffer) < end:
                    break
                raw = bytes(self.buffer[:end])
                if int.from_bytes(raw[-2:], "big") != crc16(raw[1:-2]):
                    del self.buffer[0]
                    continue
                del self.buffer[:end]
                yield raw[1], raw[4:-2]
            chunk = self.port.read(100)
            if chunk:
                self.buffer.extend(chunk)

    def exchange(self, kind: int, payload: bytes, accept, *, attempts: int = 3,
                 timeout: float = 5, retry_timeout: bool = True):
        raw = encode(kind, payload)
        for _ in range(attempts):
            if self.port.write(raw) != len(raw):
                raise OSError("Incomplete UART write")
            self.port.flush()
            try:
                for reply_kind, reply in self.receive(self.clock() + timeout):
                    if accept(reply_kind, reply):
                        return reply
            except RetryPacket:
                continue
            if not retry_timeout:
                break
        raise TimeoutError("Expected THR acknowledgement not received; transfer is not verified")

    def probe(self) -> bytes:
        def accept(kind, reply):
            if kind != 0:
                return False
            if reply != self.profile.identity_reply:
                raise ValueError("Unrecognized THR bootloader identity; no erase command sent")
            return True
        return self.exchange(0, b"\x01\x00", accept)

    def transfer(self, image: bytes, manifest: dict) -> dict:
        image_hash = admitted_image(image, manifest)
        self.probe()
        # A start acknowledgement can be lost after erase; do not repeat that boundary.
        self.exchange(1, b"\x01\x00" + len(image).to_bytes(4, "big"),
                      lambda kind, reply: kind == 1 and reply == self.profile.start_reply, attempts=1)
        for index, offset in enumerate(range(0, len(image), 1024)):
            data = image[offset:offset + 1024]
            header = index.to_bytes(4, "big") + len(data).to_bytes(2, "big")
            def accepted(kind, reply):
                if kind != 2 or len(reply) != 7 or reply[:6] != header:
                    return False
                if reply[6] == 2:
                    raise RetryPacket()
                if reply[6] != 1:
                    raise ValueError("Unexpected THR data acknowledgement status")
                return True

            # Only a valid NACK proves an unsafe-to-repeat packet was rejected.
            self.exchange(2, header + data, accepted,
                          retry_timeout=index != 0 or self.profile.packet_zero_retry_safe)
        self.exchange(1, b"\x02\x01", lambda kind, reply: kind == 1 and reply == self.profile.end_reply,
                      attempts=1)
        return {"transfer_acknowledged": True, "verified": False, "application_sha256": image_hash}


def application_session(manifest: dict, *, reset: bool = False,
                        expected_boot: bytes | None = None, capture_root: Path | None = None):
    # Reuse the installed vendor transport without its unrelated AVR reset preamble.
    sys.path.insert(0, "/home/qidi/klipper/klippy")
    import reactor
    import serial
    import serialhdl

    loop = reactor.Reactor()
    reader = serialhdl.SerialReader(loop)
    result = {}

    def run(eventtime):
        try:
            port = serial.Serial(DEVICE, 500000, timeout=0, exclusive=True)
            if not reader._start_session(port):
                raise TimeoutError("THR application identify timed out")
            constants = reader.get_msgparser().get_constants()
            if constants.get("MCU") != "stm32f103xe" or int(constants["SERIAL_BAUD"]) != 500000:
                raise ValueError("Unexpected application identity")
            def read(address, order=2):
                response = reader.send_with_response(
                    "debug_read order=%d addr=%d" % (order, address), "debug_result"
                )
                return int(response["val"])

            version, build_versions = reader.get_msgparser().get_version_info()
            metadata = {"version": version, "build_versions": build_versions,
                        "constants": {key: constants[key] for key in ("MCU", "CLOCK_FREQ", "SERIAL_BAUD") if key in constants},
                        "id_registers": {name: hex(read(address, order)) for name, address, order in (
                            ("cpuid", 0xe000ed00, 2), ("dbgmcu_idcode", 0xe0042000, 2),
                            ("flash_size_kib", 0x1ffff7e0, 1))}}
            boot = b"".join(read(address).to_bytes(4, "little")
                            for address in range(0x08000000, 0x08008000, 4))
            supported = len(boot) == 0x8000 and digest(boot) in thr_bootloaders.ADMITTED_BOOTLOADERS
            length = manifest["thr"]["size"] if supported else 0x18000
            region = b"".join(read(address).to_bytes(4, "little")
                              for address in range(0x08008000, 0x08008000 + length, 4))
            app = region[:manifest["thr"]["size"]]
            result["snapshot"] = boot, app, metadata, region
            if reset:
                if not supported:
                    if capture_root is None:
                        raise ValueError("Unrecognized installed bootloader; no reset sent")
                    directory = Path(tempfile.mkdtemp(prefix="unsupported-thr-", dir=capture_root))
                    save_snapshot(directory, boot, app, metadata=metadata, application_region=region)
                    raise ValueError("Unrecognized installed bootloader; no reset sent. Capture: " + str(directory))
                identify_bootloader(boot)
                admitted_image(app, manifest)
                if expected_boot is None or boot != expected_boot:
                    raise ValueError("Installed bootloader differs from backup; no reset sent")
                reader.send("reset")
                loop.pause(loop.monotonic() + 0.050)
        except Exception as exc:
            result["error"] = exc
        finally:
            reader.disconnect()
            loop.end()

    def timed_out(signum, frame):
        raise TimeoutError("THR application operation exceeded 900 seconds")

    previous_handler = signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(900)
    loop.register_callback(run)
    try:
        loop.run()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
        loop.finalize()
    if "error" in result:
        raise result["error"]
    return result["snapshot"]


def save_snapshot(directory: Path, boot: bytes, app: bytes, *, metadata=None,
                  application_region: bytes | None = None) -> dict:
    report = {"bootloader_sha256": digest(boot), "application_sha256": digest(app),
              "supported_bootloader": len(boot) == 0x8000 and digest(boot) in thr_bootloaders.ADMITTED_BOOTLOADERS,
              "bootloader_page_sha256": [digest(boot[offset:offset + 2048]) for offset in range(0, len(boot), 2048)],
              **(metadata or {})}
    files = {"bootloader.bin": boot, "application.bin": app}
    if application_region is not None:
        files["application-region.bin"] = application_region
        report.update(application_region_sha256=digest(application_region), application_region_bytes=len(application_region))
    files["snapshot.json"] = (json.dumps({key: report[key] for key in ("bootloader_sha256", "application_sha256")}, indent=2) + "\n").encode()
    files["report.json"] = (json.dumps(report, indent=2) + "\n").encode()
    for name, data in files.items():
        with os.fdopen(os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("snapshot", "probe", "transfer", "verify"))
    parser.add_argument("--image", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--original-backup-dir", type=Path, help="verify bootloader unchanged from this pre-transfer snapshot")
    parser.add_argument("--printer-idle-confirmed", action="store_true")
    parser.add_argument("--reset", action="store_true", help="read and admit the running application before THR reset")
    parser.add_argument("--confirm-write", action="store_true", help="allow application erase and programming")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if args.reset and args.operation not in ("probe", "transfer"):
            raise ValueError("--reset is only used by probe or transfer")
        if args.confirm_write and args.operation != "transfer":
            raise ValueError("--confirm-write is only used by transfer")
        if args.image is not None and args.operation not in ("transfer", "verify"):
            raise ValueError("--image is only used by transfer or verify")
        if args.original_backup_dir is not None and args.operation != "verify":
            raise ValueError("--original-backup-dir is only used by verify")
        image = None
        if args.operation in ("transfer", "verify"):
            if args.image is None:
                raise ValueError("--image is required")
            image = args.image.read_bytes()
            admitted_image(image, manifest)
        if args.operation == "verify":
            if args.backup_dir is None:
                raise ValueError("--backup-dir must identify the readback snapshot")
            original_boot = load_backup(args.original_backup_dir, manifest)[0] if args.original_backup_dir else None
            print(json.dumps(verify_readback(image, args.backup_dir, manifest, expected_bootloader=original_boot), indent=2))
            return 0
        if args.operation == "transfer" and not args.confirm_write:
            raise ValueError("Transfer requires --confirm-write; application erase was not requested")
        backup = None
        if args.operation in ("probe", "transfer"):
            if args.backup_dir is None:
                raise ValueError("--backup-dir with validated stock application and bootloader is required")
            backup = load_backup(args.backup_dir, manifest)
            if digest(backup[1]) != manifest["thr"]["stock_sha256"]:
                raise ValueError("Keep an admitted stock application as the recovery backup")
        if args.operation == "snapshot":
            if args.output_dir is None or args.output_dir.exists() or args.output_dir.is_symlink():
                raise ValueError("Snapshot needs a new --output-dir")
        elif args.output_dir is not None:
            raise ValueError("--output-dir is only used by snapshot")
        require_ownership(args.printer_idle_confirmed)
        if args.operation == "snapshot":
            args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
            boot, app, metadata, region = application_session(manifest)
            report = save_snapshot(args.output_dir, boot, app, metadata=metadata, application_region=region)
            if not report["supported_bootloader"]:
                print(json.dumps({"unsupported_bootloader": True, "firmware_changed": False,
                                  "summary": str(args.output_dir / "report.json")}, indent=2))
                return UNSUPPORTED_BOOTLOADER
            identify_bootloader(boot)
            admitted_image(app, manifest)
            print(json.dumps({"application_sha256": digest(app), "bootloader_sha256": digest(boot)}, indent=2))
            return 0
        profile = identify_bootloader(backup[0])
        if args.reset:
            application_session(manifest, reset=True, expected_boot=backup[0], capture_root=args.backup_dir.parent)
            time.sleep(1)
        import serial
        with serial.Serial(DEVICE, 115200, timeout=0.05, write_timeout=2, exclusive=True) as port:
            client = Bootloader(port, profile)
            if args.operation == "probe":
                reply = client.probe()
                print(json.dumps({"bootloader_reply": reply.hex(), "erase_requested": False}, indent=2))
            else:
                print(json.dumps(client.transfer(image, manifest), indent=2))
        print("Keep services stopped until the application returns; use snapshot and verify for readback.", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"THR operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    raise SystemExit(main())
