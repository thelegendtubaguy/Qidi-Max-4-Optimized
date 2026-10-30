#!/usr/bin/env python3
"""Restricted QIDI Box (USB) snapshots, transfers, and readback verification."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

if __package__:
    from .build_box_firmware import PATCH_MANIFEST, load_manifest
else:
    from build_box_firmware import PATCH_MANIFEST, load_manifest

UNSUPPORTED = 3
SERVICES = ("klipper.service", "qidi-client.service", "tltg-optimized-auto-update.timer")
APP_IDS = ("1d50", "614e")
BOOT_IDS = ("0483", "5740")
BOOTLOADER_BYTES = 0x8000
APPLICATION_BASE = 0x08008000
APPLICATION_REGION = 0x18000
USB_PATH = re.compile(r"^\d+-\d+(\.\d+)*$")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def image_identity(data: bytes, manifest: dict) -> str | None:
    box = manifest["box"]
    if len(data) != box["size"]:
        return None
    return {box["stock_sha256"]: "stock", box["patched_sha256"]: "patched"}.get(digest(data))


def admitted_image(data: bytes, manifest: dict) -> str:
    identity = image_identity(data, manifest)
    if identity is None:
        raise ValueError("Unrecognized Box image")
    return identity


def bootloader_profile(data: bytes, manifest: dict) -> dict:
    for profile in manifest["bootloaders"]:
        if len(data) == BOOTLOADER_BYTES and digest(data) == profile["sha256"]:
            return profile
    raise ValueError("Unrecognized Box bootloader")


def load_backup(directory: Path, manifest: dict) -> tuple[bytes, bytes]:
    boot = (directory / "bootloader.bin").read_bytes()
    app = (directory / "application.bin").read_bytes()
    bootloader_profile(boot, manifest)
    admitted_image(app, manifest)
    return boot, app


def verify_readback(image: bytes, directory: Path, manifest: dict, *, expected_bootloader: bytes | None = None) -> dict:
    identity = admitted_image(image, manifest)
    boot, app = load_backup(directory, manifest)
    if expected_bootloader is not None and boot != expected_bootloader:
        raise ValueError("Bootloader readback differs from the original backup")
    if app != image:
        raise ValueError("Application readback does not match the selected image")
    return {"verified": True, "application": identity, "application_sha256": digest(app),
            "bootloader_sha256": digest(boot)}


def require_ownership(idle_confirmed: bool) -> None:
    if not idle_confirmed:
        raise ValueError("Confirm idle state and zero heater targets with --printer-idle-confirmed")
    for service in SERVICES:
        result = subprocess.run(["systemctl", "show", service, "--property=LoadState,ActiveState"],
                                capture_output=True, text=True, timeout=5)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if values.get("LoadState") == "not-found" and service.endswith(".timer"):
            continue
        if result.returncode or values.get("ActiveState") != "inactive":
            raise ValueError(f"Stop {service} before Box serial access")


def crc16(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xA001 if value & 1 else 0)
    return value ^ 0xFFFF


def encode(kind: int, payload: bytes) -> bytes:
    body = bytes([kind]) + len(payload).to_bytes(2, "big") + payload
    return b"\xa5" + body + crc16(body).to_bytes(2, "big")


class TransferFailed(Exception):
    pass


class Bootloader:
    """Box bootloader client. Start erases sectors 2-5; data is written at a
    pointer that only rewinds at reset, so start and packet 0 are never resent.
    Resending the immediately previous data packet is acknowledged without a
    second write. Any failure leaves the session to time out, which erases the
    first application sector and keeps the bootloader resident."""
    IDENTITY_WAIT = 0.4
    START_TIMEOUT = 20.0
    ACK_TIMEOUT = 0.6
    DATA_TRIES = 3

    def __init__(self, port, profile: dict, clock=time.monotonic):
        self.port, self.clock = port, clock
        self.identity_reply = bytes.fromhex(profile["identity_reply"])
        self.buffer = bytearray()
        self.events: list = []

    def _frames(self, deadline: float):
        while self.clock() < deadline:
            while len(self.buffer) >= 6:
                if self.buffer[0] != 0xA5:
                    del self.buffer[0]
                    continue
                size = int.from_bytes(self.buffer[2:4], "big")
                if size > 64:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < size + 6:
                    break
                raw = bytes(self.buffer[:size + 6])
                del self.buffer[:size + 6]
                if int.from_bytes(raw[-2:], "big") == crc16(raw[1:-2]):
                    yield raw[1], raw[4:-2]
            chunk = self.port.read(64)
            if chunk:
                self.buffer.extend(chunk)

    def _send(self, kind: int, payload: bytes) -> None:
        raw = encode(kind, payload)
        if self.port.write(raw) != len(raw):
            raise OSError("Incomplete USB write")
        self.port.flush()

    def _await(self, timeout: float, accept):
        for kind, payload in self._frames(self.clock() + timeout):
            if accept(kind, payload):
                return kind, payload
        return None

    def probe(self) -> bytes:
        # The bootloader answers identity once per boot; a repeat is harmless.
        for _ in range(3):
            self._send(0, b"\x01\x00")
            got = self._await(self.IDENTITY_WAIT, lambda kind, payload: kind == 0)
            if got:
                if got[1] != self.identity_reply:
                    raise ValueError("Unrecognized Box bootloader identity; no erase command sent")
                return got[1]
        raise TransferFailed("No bootloader identity reply; nothing was erased")

    def transfer(self, image: bytes, manifest: dict) -> dict:
        identity = admitted_image(image, manifest)
        self.probe()
        self._send(1, b"\x01\x00" + len(image).to_bytes(4, "big"))
        if not self._await(self.START_TIMEOUT, lambda kind, payload: kind == 1 and payload == b"\x01\x01"):
            raise TransferFailed("Start was not acknowledged")
        index = 0
        for index, offset in enumerate(range(0, len(image), 1024)):
            data = image[offset:offset + 1024]
            header = index.to_bytes(4, "big") + len(data).to_bytes(2, "big")
            for attempt in range(self.DATA_TRIES):
                self._send(2, header + data)
                got = self._await(self.ACK_TIMEOUT,
                                  lambda kind, payload: kind == 2 and len(payload) == 7 and payload[:6] == header)
                if got and got[1][6] == 1:
                    break
                if index == 0 and not (got and got[1][6] == 2):
                    # Only a CRC rejection proves packet 0 was not written.
                    raise TransferFailed("Packet 0 was not acknowledged")
                self.events.append({"retry": index, "attempt": attempt})
            else:
                raise TransferFailed(f"Packet {index} was not acknowledged")
        self._send(1, b"\x02\x01")
        if not self._await(2.0, lambda kind, payload: kind == 1 and payload == b"\x02\x01"):
            raise TransferFailed("End was not acknowledged")
        return {"transfer_acknowledged": True, "verified": False, "application": identity,
                "application_sha256": digest(image), "packets": index + 1, "events": self.events}


# ---- printer side ----------------------------------------------------------

def usb_state(usb_path: str) -> tuple[tuple[str, str] | None, str | None]:
    base = Path("/sys/bus/usb/devices") / usb_path
    try:
        ids = tuple((base / name).read_text().strip() for name in ("idVendor", "idProduct"))
    except OSError:
        return None, None
    for interface in sorted(base.glob(usb_path + ":*")):
        ttys = sorted((interface / "tty").glob("*")) if (interface / "tty").is_dir() else []
        if ttys:
            return ids, "/dev/" + ttys[0].name
    return ids, None


def wait_for(usb_path: str, ids: tuple[str, str], timeout: float) -> str:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        state, tty = usb_state(usb_path)
        # udev grants access a moment after the device node appears.
        if state == ids and tty and os.access(tty, os.R_OK | os.W_OK):
            return tty
        time.sleep(0.01)
    raise TimeoutError(f"Box {usb_path} did not appear as {ids[0]}:{ids[1]}")


def application_session(tty: str, manifest: dict, *, application: bool = True, reset_expected_boot: bytes | None = None):
    # Reuse the installed Klipper transport.
    sys.path.insert(0, "/home/qidi/klipper/klippy")
    import reactor
    import serial
    import serialhdl

    loop = reactor.Reactor()
    reader = serialhdl.SerialReader(loop)
    result = {}

    def run(eventtime):
        try:
            port = serial.Serial(tty, 250000, timeout=0, exclusive=True)
            if not reader._start_session(port):
                raise TimeoutError("Box application identify timed out")
            parser = reader.get_msgparser()
            constants = parser.get_constants()
            if constants.get("MCU") != "stm32f401xc":
                raise ValueError("Unexpected application identity")

            def block(start, end):
                return b"".join((int(reader.send_with_response(
                    "debug_read order=2 addr=%d" % address, "debug_result")["val"]) & 0xFFFFFFFF
                ).to_bytes(4, "little") for address in range(start, end, 4))

            version, build_versions = parser.get_version_info()
            metadata = {"version": version, "build_versions": build_versions,
                        "constants": {key: constants[key] for key in ("MCU", "CLOCK_FREQ") if key in constants}}
            boot = block(0x08000000, 0x08000000 + BOOTLOADER_BYTES)
            region = b""
            if application:
                supported = any(digest(boot) == p["sha256"] for p in manifest["bootloaders"])
                # Admitted boards: the image plus its 1 KiB padding; otherwise the whole region.
                length = ((manifest["box"]["size"] + 1023) // 1024 + 1) * 1024 if supported else APPLICATION_REGION
                region = block(APPLICATION_BASE, APPLICATION_BASE + length)
            result["snapshot"] = boot, region, metadata
            if reset_expected_boot is not None:
                if boot != reset_expected_boot:
                    raise ValueError("Installed bootloader differs from backup; no reset sent")
                reader.send("reset")
                loop.pause(loop.monotonic() + 0.050)
        except Exception as exc:
            result["error"] = exc
        finally:
            reader.disconnect()
            loop.end()

    def timed_out(signum, frame):
        raise TimeoutError("Box application operation exceeded 600 seconds")

    previous = signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(600)
    loop.register_callback(run)
    try:
        loop.run()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
        loop.finalize()
    if "error" in result:
        raise result["error"]
    return result["snapshot"]


def save_snapshot(directory: Path, boot: bytes, region: bytes, manifest: dict, *, metadata=None) -> dict:
    size = manifest["box"]["size"]
    app = region[:size]
    supported = any(len(boot) == BOOTLOADER_BYTES and digest(boot) == p["sha256"] for p in manifest["bootloaders"])
    identity = image_identity(app, manifest)
    padded = (size + 1023) // 1024 * 1024
    report = {"bootloader_sha256": digest(boot), "supported_bootloader": supported,
              "application_sha256": digest(app), "application": identity or "unrecognized",
              "application_padding": sorted(set(region[size:padded])),
              "bootloader_page_sha256": [digest(boot[offset:offset + 2048]) for offset in range(0, len(boot), 2048)],
              **(metadata or {})}
    files = {"bootloader.bin": boot, "application.bin": app}
    if not supported or identity is None:
        files["application-region.bin"] = region
        report.update(application_region_sha256=digest(region), application_region_bytes=len(region))
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
    parser.add_argument("operation", choices=("snapshot", "transfer", "verify"))
    parser.add_argument("--usb", help="sysfs USB path of the Box MCU, for example 2-1.4.2")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--original-backup-dir", type=Path, help="verify the bootloader is unchanged from this snapshot")
    parser.add_argument("--printer-idle-confirmed", action="store_true")
    parser.add_argument("--confirm-write", action="store_true", help="allow application erase and programming")
    parser.add_argument("--rescue", action="store_true", help="transfer to a Box that is in, or is power-cycled into, its bootloader")
    parser.add_argument("--wait", type=float, default=0.0, help="seconds to wait for the Box application or bootloader")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(PATCH_MANIFEST)
        if args.usb is not None and not USB_PATH.match(args.usb):
            raise ValueError("Invalid USB path")
        if args.operation == "verify":
            if args.image is None or args.backup_dir is None:
                raise ValueError("verify needs --image and --backup-dir")
            original = load_backup(args.original_backup_dir, manifest)[0] if args.original_backup_dir else None
            print(json.dumps(verify_readback(args.image.read_bytes(), args.backup_dir, manifest,
                                             expected_bootloader=original), indent=2))
            return 0
        if args.usb is None:
            raise ValueError("--usb is required")
        if args.operation == "snapshot":
            if args.output_dir is None or args.output_dir.exists() or args.output_dir.is_symlink():
                raise ValueError("Snapshot needs a new --output-dir")
            require_ownership(args.printer_idle_confirmed)
            tty = wait_for(args.usb, APP_IDS, args.wait) if args.wait else None
            if tty is None:
                ids, tty = usb_state(args.usb)
                if ids != APP_IDS or tty is None:
                    raise ValueError("The Box application is not running")
            args.output_dir.mkdir(mode=0o700, parents=True)
            boot, region, metadata = application_session(tty, manifest)
            report = save_snapshot(args.output_dir, boot, region, manifest, metadata=metadata)
            summary = {key: report[key] for key in ("application", "application_sha256", "bootloader_sha256",
                                                     "supported_bootloader", "version")}
            print(json.dumps(summary, indent=2))
            return 0 if report["supported_bootloader"] and report["application"] != "unrecognized" else UNSUPPORTED
        # transfer
        if not args.confirm_write:
            raise ValueError("Transfer requires --confirm-write; application erase was not requested")
        if args.image is None or args.backup_dir is None:
            raise ValueError("transfer needs --image and --backup-dir")
        image = args.image.read_bytes()
        admitted_image(image, manifest)
        boot, _ = load_backup(args.backup_dir, manifest)
        profile = bootloader_profile(boot, manifest)
        require_ownership(args.printer_idle_confirmed)
        import serial
        if args.rescue:
            print("Waiting for the Box bootloader; power-cycle the Box now if it is not already waiting.", file=sys.stderr)
            tty = wait_for(args.usb, BOOT_IDS, args.wait or 300.0)
        else:
            ids, tty = usb_state(args.usb)
            if ids != APP_IDS or tty is None:
                raise ValueError("The Box application is not running; use --rescue")
            application_session(tty, manifest, application=False, reset_expected_boot=boot)
            tty = wait_for(args.usb, BOOT_IDS, 5.0)
        with serial.Serial(tty, 115200, timeout=0.02, write_timeout=2, exclusive=True) as port:
            print(json.dumps(Bootloader(port, profile).transfer(image, manifest), indent=2))
        print("Wait for the Box application, then use snapshot and verify for readback.", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"Box operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    raise SystemExit(main())
