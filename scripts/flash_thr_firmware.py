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
FELL_BACK = 4
END_UNCONFIRMED = 5
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


class RecoveryFailed(Exception):
    pass


class Bootloader:
    HOLD_SECONDS = 120.0
    PAIR_INTERVAL = 0.2

    def __init__(self, port, profile, clock=time.monotonic, sleep=time.sleep):
        self.port = port
        self.profile = profile
        self.clock = clock
        self.sleep = sleep
        self.buffer = bytearray()
        self.last_sent = None
        self.last_reply = None
        self.events = []

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

    # Recovery relies on the recoverable profile's measured session, exit and
    # startup timers; see the second-build entries in openspec/observations/qidi-platform.md.
    def transfer_recovering(self, image: bytes, fallback: bytes, manifest: dict) -> dict:
        if not self.profile.recoverable:
            raise ValueError("Transfer recovery is not validated for this bootloader")
        image_hash = admitted_image(image, manifest)
        if admitted_image(fallback, manifest) != manifest["thr"]["stock_sha256"] or len(fallback) != len(image):
            raise ValueError("The recovery fallback must be the admitted stock application")
        self.probe()
        self.last_reply = self.clock()
        target, started = image, False
        for _ in range(4):
            outcome = self._program(target, started)
            if outcome in ("done", "unconfirmed-end"):
                return {"transfer_acknowledged": outcome == "done", "verified": False,
                        "application_sha256": digest(target), "requested_sha256": image_hash,
                        "fell_back": target is not image, "events": self.events}
            target = fallback
            started = outcome == "ambiguous" and self._await_reset(len(fallback))
        raise RecoveryFailed("Fallback transfer failed repeatedly; THR state is unknown")

    def _log(self, event, **extra):
        self.events.append({"t": round(self.clock(), 3), "event": event, **extra})

    def _send(self, kind: int, payload: bytes) -> None:
        raw = encode(kind, payload)
        if self.port.write(raw) != len(raw):
            raise OSError("Incomplete UART write")
        self.port.flush()
        self.last_sent = self.clock()

    def _wait(self, seconds: float, accept):
        for kind, reply in self.receive(self.clock() + seconds):
            self.last_reply = self.clock()
            if accept(kind, reply):
                return kind, reply
        return None

    def _is_identity(self, kind, reply):
        return kind == 0 and reply == self.profile.identity_reply

    def _is_start(self, kind, reply):
        return kind == 1 and reply == self.profile.start_reply

    def _identity_probe(self, seconds: float) -> bool:
        end = self.clock() + seconds
        while self.clock() < end:
            self._send(0, b"\x01\x00")
            if self._wait(self.PAIR_INTERVAL, self._is_identity):
                return True
        return False

    def _await_reset(self, size: int) -> bool:
        session, exit_delay = self.profile.session_ticks / 1000, self.profile.exit_ticks / 1000
        remaining = self.last_sent + session + exit_delay + 0.2 - self.clock()
        if remaining > 0:
            self.sleep(remaining)
        # Start is only sent once the board has certainly reset: in a session that
        # already holds data it re-erases without rewinding the write position.
        end = self.clock() + 2 * self.profile.startup_ticks / 1000
        start = b"\x01\x00" + size.to_bytes(4, "big")
        while self.clock() < end:
            self._send(0, b"\x01\x00")
            self._wait(self.PAIR_INTERVAL / 2, self._is_identity)
            self._send(1, start)
            if self._wait(self.PAIR_INTERVAL / 2, self._is_start):
                self._log("restarted")
                return True
        self._log("start-unconfirmed")
        return False

    def _hold(self, kind, payload, accept, hold, label, probe=None):
        probe = probe or (kind, payload, accept)
        stale = self.profile.session_ticks / 1000 - 1.0
        deadline = self.clock() + hold
        tries = quiet = 0
        heard = self.last_reply
        while self.clock() < deadline:
            silent = heard is not None and self.clock() - heard >= stale
            use = (kind, payload, accept)
            if silent:
                quiet += 1
                use = probe if quiet % 5 == 1 else None
            if use is not None:
                k, p, acc = use
                self._send(k, p)
                got = self._wait(2.0 if tries == 0 else 0.2,
                                 lambda a, b, acc=acc: acc(a, b) or self._is_identity(a, b))
                tries += 1
                if got and self._is_identity(*got):
                    self._log("fresh-during-hold", at=label)
                    return "fresh"
                if got and not (got[0] == 2 and got[1][6] == 2):
                    if silent or (heard is not None and self.last_reply - heard >= stale):
                        # In the gap between a session timeout and its reset the
                        # bootloader still acknowledges; only identity tells.
                        self._log("late-ack", at=label)
                        if self._identity_probe(self.profile.exit_ticks / 1000 + 1.0):
                            return "fresh"
                        return "ambiguous"
                    if tries > 1:
                        self._log("resumed", at=label, tries=tries)
                    return got
                if got:
                    heard = self.last_reply
            self._send(0, b"\x01\x00")
            if self._wait(0.2, self._is_identity):
                self._log("fresh-during-hold", at=label)
                return "fresh"
        return None

    def _program(self, image: bytes, started: bool) -> str:
        if not started:
            start = b"\x01\x00" + len(image).to_bytes(4, "big")
            for attempt in range(3):
                self._send(1, start)
                if self._wait(5 if attempt == 0 else 1, self._is_start):
                    break
            else:
                self._log("start-unacknowledged")
        for index, offset in enumerate(range(0, len(image), 1024)):
            data = image[offset:offset + 1024]
            header = index.to_bytes(4, "big") + len(data).to_bytes(2, "big")

            def ack(kind, reply, header=header):
                return kind == 2 and len(reply) == 7 and reply[:6] == header and reply[6] in (1, 2)
            if index == 0:
                while True:
                    self._send(2, header + data)
                    got = self._wait(5, ack)
                    if got is None:
                        self._log("packet0-unacknowledged")
                        return "ambiguous"
                    if got[1][6] == 1:
                        break
                continue
            got = self._hold(2, header + data, ack, self.HOLD_SECONDS, index)
            if got in ("fresh", "ambiguous"):
                return got
            if got is None:
                raise RecoveryFailed(f"No reply for {self.HOLD_SECONDS:.0f} s at packet {index}; THR state is unknown")
        last = (2, header + data, ack)
        got = self._hold(1, b"\x02\x01", lambda kind, reply: kind == 1 and reply == self.profile.end_reply,
                         2 * (self.profile.session_ticks + self.profile.exit_ticks) / 1000, "end", probe=last)
        if got in ("fresh", "ambiguous"):
            return got
        return "done" if got else "unconfirmed-end"


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
    parser.add_argument("--recover-to-stock", action="store_true",
                        help="on a failed exchange, resume, or program the backup's stock application")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if args.recover_to_stock and args.operation != "transfer":
            raise ValueError("--recover-to-stock is only used by transfer")
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
            if args.recover_to_stock and not identify_bootloader(backup[0]).recoverable:
                raise ValueError("Transfer recovery is not validated for this bootloader")
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
            elif args.recover_to_stock:
                try:
                    result = client.transfer_recovering(image, backup[1], manifest)
                except RecoveryFailed:
                    print(json.dumps({"recovered": False, "events": client.events}, indent=2))
                    raise
                print(json.dumps(result, indent=2))
            else:
                print(json.dumps(client.transfer(image, manifest), indent=2))
        print("Keep services stopped until the application returns; use snapshot and verify for readback.", file=sys.stderr)
        if args.recover_to_stock and result["fell_back"]:
            return FELL_BACK
        if args.recover_to_stock and not result["transfer_acknowledged"]:
            return END_UNCONFIRMED
        return 0
    except Exception as exc:
        print(f"THR operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    raise SystemExit(main())
