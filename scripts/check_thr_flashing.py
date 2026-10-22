#!/usr/bin/env python3
"""Check THR transfer safety offline; optionally execute a captured bootloader."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import struct
import sys
import tempfile
from types import SimpleNamespace
from collections import deque
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import flash_thr_firmware as tool
from thr_bootloaders import FIRST, PROFILES, identify_bootloader


class NativeBoard:
    def __init__(self, boot: bytes, application: bytes):
        self.profile = identify_bootloader(boot, admitted=False)
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
        self.r0, self.r1, self.r2 = UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2
        self.sp, self.lr, self.pc = UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        for address, size in ((0x08000000, 0x20000), (0x20000000, 0x10000),
                              (0x40000000, 0x30000), (0xe000e000, 0x2000)):
            self.uc.mem_map(address, size)
        self.uc.mem_write(0x08000000, boot)
        self.uc.mem_write(0x08008000, b"\xff" * 0x18000)
        self.uc.mem_write(0x08008000, application)
        self.boot = boot
        self.sent, self.erases, self.writes, self.jumps, self.resets = [], [], [], [], []
        self.uc.hook_add(UC_HOOK_CODE, self.hook)
        for address in self.profile.initialize:
            self.call(address)
        if self.profile.startup_ticks is not None:
            # main() loads this counter after peripheral initialization.
            self.uc.mem_write(self.profile.session_timer, struct.pack("<I", self.profile.startup_ticks))

    def call(self, address, *args):
        self.uc.reg_write(self.sp, 0x2000f000)
        self.uc.reg_write(self.lr, 0x2000fff1)
        for reg, value in zip((self.r0, self.r1, self.r2), args):
            self.uc.reg_write(reg, value)
        self.uc.emu_start(address | 1, 0x2000fff0, count=2000000)
        assert self.uc.reg_read(self.pc) == 0x2000fff0, "Bootloader execution bound exceeded"
        return self.uc.reg_read(self.r0)

    def ret(self, value=0):
        self.uc.reg_write(self.r0, value)
        self.uc.reg_write(self.pc, self.uc.reg_read(self.lr))

    def hook(self, uc, address, size, data):
        # Only flash-controller register operations and UART output are replaced.
        if address in self.profile.controller_hooks:
            self.ret()
        elif address == self.profile.erase_hook:
            destination = uc.reg_read(self.r0)
            start, end, page_size = self.profile.erase_range
            assert start <= destination <= end - page_size and destination % page_size == 0
            self.erases.append(destination)
            uc.mem_write(destination, b"\xff" * page_size)
            self.ret()
        elif address == self.profile.program_hook:
            destination, value = uc.reg_read(self.r0), uc.reg_read(self.r1)
            assert 0x08008000 <= destination <= 0x0801fffc and destination % 4 == 0
            word = struct.pack("<I", value)
            previous = bytes(uc.mem_read(destination, 4))
            assert all((old & new) == new for old, new in zip(previous, word))
            uc.mem_write(destination, word)
            self.writes.append(destination)
            self.ret()
        elif address == self.profile.send_hook:
            raw = bytes(uc.mem_read(uc.reg_read(self.r0), uc.reg_read(self.r1)))
            assert int.from_bytes(raw[-2:], "big") == tool.crc16(raw[1:-2])
            self.sent.append(raw)
            self.ret()
        elif address in (self.profile.jump_hook, self.profile.reset_hook):
            if address == self.profile.jump_hook:
                self.jumps.append(0x08008000)
            else:
                self.resets.append(address)
            self.uc.reg_write(self.pc, 0x2000fff0)
            self.uc.emu_stop()

    def receive(self, raw):
        start = len(self.sent)
        self.uc.mem_write(self.profile.receive_buffer, raw)
        for address in self.profile.receive_flags:
            self.uc.mem_write(address, b"\x01")
        self.call(self.profile.dispatch)
        assert bytes(self.uc.mem_read(0x08000000, 0x8000)) == self.boot
        return self.sent[start:]

    def application(self, size):
        return bytes(self.uc.mem_read(0x08008000, size))

    def timeout(self):
        self.uc.mem_write(self.profile.session_timer, b"\x00" * 4)
        self.call(self.profile.dispatch)
        self.uc.mem_write(self.profile.exit_timer, b"\x00" * 4)
        self.call(self.profile.dispatch)

    def advance(self, ticks):
        assert self.profile.tick is not None
        for _ in range(ticks):
            self.call(self.profile.tick)
            self.call(self.profile.dispatch)


class Peer:
    def __init__(self, mode="normal", board=None, profile=FIRST):
        self.mode, self.board = mode, board
        self.profile = board.profile if board else profile
        self.queue = bytearray(b"noise\xa5\xff\xff\xff")
        self.now = 0.0
        self.sent = []
        self.pages = {}
        self.injected = False
        self.erased = False
        self.fragments = deque((1, 2, 5, 3, 11))

    def clock(self):
        return self.now

    def flush(self):
        pass

    def read(self, count):
        self.now += 0.05
        chunk_size = self.fragments[0]
        self.fragments.rotate(-1)
        count = min(count, chunk_size)
        chunk = bytes(self.queue[:count])
        del self.queue[:count]
        return chunk

    def write(self, raw):
        assert raw[0] == 0xa5
        assert int.from_bytes(raw[2:4], "big") + 6 == len(raw)
        assert int.from_bytes(raw[-2:], "big") == tool.crc16(raw[1:-2])
        kind, payload = raw[1], raw[4:-2]
        self.sent.append((kind, payload))
        if kind == 1 and len(payload) == 6:
            self.erased = True
        if self.mode == "silent":
            return len(raw)
        if self.mode == "wrong-board":
            self.queue.extend(tool.encode(0, b"\x01\x03\x01\x02"))
            return len(raw)
        corrupt = kind == 2 and self.mode == "bad-data" and not self.injected
        transmitted = raw[:-1] + bytes([raw[-1] ^ 1]) if corrupt else raw
        if self.board:
            replies = self.board.receive(transmitted)
        elif kind == 0:
            replies = [tool.encode(0, self.profile.identity_reply)]
        elif kind == 1:
            replies = [tool.encode(1, b"\x01\x01" if len(payload) == 6 else b"\x02\x01")]
        else:
            index = int.from_bytes(payload[:4], "big")
            assert int.from_bytes(payload[4:6], "big") == len(payload) - 6
            if not corrupt:
                if index in self.pages:
                    assert self.pages[index] == payload[6:]
                self.pages[index] = payload[6:]
            replies = [tool.encode(2, payload[:6] + (b"\x02" if corrupt else b"\x01"))]
        inject_here = (kind == 2 and not self.injected
                       and (int.from_bytes(payload[:4], "big") == 1
                            or self.mode in ("bad-data", "first-bad-reply", "first-lost-ack")))
        if inject_here:
            if self.mode in ("bad-reply", "first-bad-reply"):
                replies = [reply[:-1] + bytes([reply[-1] ^ 1]) for reply in replies]
                self.injected = True
            elif self.mode in ("lost-ack", "first-lost-ack"):
                replies = []
                self.injected = True
            elif self.mode == "stale-ack":
                replies = [tool.encode(2, b"\x00\x00\x00\x99\x04\x00\x01")]
                self.injected = True
            elif corrupt:
                self.injected = True
        if kind == 1 and ((self.mode == "lost-start-ack" and len(payload) == 6)
                          or (self.mode == "lost-end-ack" and len(payload) == 2)):
            replies = []
        self.queue.extend(b"".join(replies))
        return len(raw)


def check_admission(stock, patched, boot, manifest, profile):
    with tempfile.TemporaryDirectory(prefix="thr-transfer-check-") as temporary:
        root = Path(temporary)
        backup = root / "backup"
        backup.mkdir()
        tool.save_snapshot(backup, boot, stock)
        stock_path, patched_path = root / "stock.bin", root / "patched.bin"
        stock_path.write_bytes(stock)
        patched_path.write_bytes(patched)
        invalid = root / "unknown.bin"
        invalid.write_bytes(patched[:-1] + bytes([patched[-1] ^ 1]))
        cases = [
            ["transfer", "--image", str(invalid), "--confirm-write", "--backup-dir", str(backup)],
            ["transfer", "--image", str(patched_path), "--backup-dir", str(backup)],
            ["transfer", "--image", str(patched_path), "--confirm-write"],
            ["transfer", "--image", str(patched_path), "--confirm-write", "--backup-dir", str(backup)],
            ["probe", "--backup-dir", str(backup)],
            ["snapshot", "--output-dir", str(backup)],
            ["snapshot", "--output-dir", str(root / "new")],
        ]
        if profile.sha256 in tool.thr_bootloaders.ADMITTED_BOOTLOADERS:
            for args in cases:
                with patch.object(tool.subprocess, "run", side_effect=AssertionError("Admission opened service access")):
                    with contextlib.redirect_stderr(io.StringIO()):
                        assert tool.main(args) == 1
            result = tool.verify_readback(stock, backup, manifest)
            assert result["verified"]
            try:
                tool.verify_readback(patched, backup, manifest)
            except ValueError:
                pass
            else:
                raise AssertionError("Mismatched readback was accepted")
            for filename, damaged in (("bootloader.bin", boot[:-1]), ("application.bin", stock[:-1])):
                target = backup / filename
                original = target.read_bytes()
                target.write_bytes(damaged)
                try:
                    with patch.object(tool.subprocess, "run", side_effect=AssertionError("Invalid backup opened service access")):
                        with contextlib.redirect_stderr(io.StringIO()):
                            assert tool.main(["transfer", "--image", str(patched_path), "--confirm-write",
                                              "--backup-dir", str(backup), "--printer-idle-confirmed"]) == 1
                finally:
                    target.write_bytes(original)
            for state in ("active", "activating", "deactivating", "failed", ""):
                with patch.object(tool.subprocess, "run", return_value=type("Result", (), {"stdout": state, "returncode": 0})()):
                    with contextlib.redirect_stderr(io.StringIO()):
                        assert tool.main(["transfer", "--image", str(patched_path), "--confirm-write",
                                          "--backup-dir", str(backup), "--printer-idle-confirmed"]) == 1

            def absent_timer(command, **kwargs):
                missing = command[2] == "tltg-optimized-auto-update.timer"
                output = "not-found" if "--property=LoadState" in command else "inactive"
                return type("Result", (), {"stdout": output, "returncode": 1 if missing else 0})()
            with patch.object(tool.subprocess, "run", side_effect=absent_timer):
                tool.require_ownership(True)
        with patch.object(tool.thr_bootloaders, "ADMITTED_BOOTLOADERS", frozenset()):
            for operation in ("probe", "transfer"):
                arguments = [operation, "--backup-dir", str(backup), "--printer-idle-confirmed", "--reset"]
                if operation == "transfer":
                    arguments += ["--image", str(patched_path), "--confirm-write"]
                with patch.object(tool.subprocess, "run", side_effect=AssertionError("Unadmitted backup opened services/UART")):
                    with contextlib.redirect_stderr(io.StringIO()):
                        assert tool.main(arguments) == 1
            try:
                tool.verify_readback(stock, backup, manifest)
            except ValueError:
                pass
            else:
                raise AssertionError("Unadmitted profile was accepted")


def check_capture(stock, boot, manifest):
    flash = boot + stock + b"\xff" * (0x18000 - len(stock))
    commands = []
    addresses = []
    constants = {"MCU": "stm32f103xe", "SERIAL_BAUD": 500000, "CLOCK_FREQ": 72000000}
    parser = SimpleNamespace(get_constants=lambda: constants, get_version_info=lambda: ("vendor", "build"))

    class Loop:
        def register_callback(self, callback):
            self.callback = callback
        def run(self):
            self.callback(0)
        def end(self):
            pass
        def finalize(self):
            pass

    class Reader:
        def __init__(self, loop):
            pass
        def _start_session(self, port):
            return True
        def get_msgparser(self):
            return parser
        def send_with_response(self, command, response):
            commands.append(command)
            _, order, address = command.split()
            address, order = int(address.split("=")[1]), int(order.split("=")[1])
            addresses.append(address)
            if address in (0xe000ed00, 0xe0042000, 0x1ffff7e0):
                return {"val": {0xe000ed00: 0x410fc241, 0xe0042000: 0x21040414, 0x1ffff7e0: 128}[address]}
            assert order == 2 and 0x08000000 <= address <= 0x0801fffc, "Read escaped flash/ID-register allowlist"
            return {"val": int.from_bytes(flash[address - 0x08000000:address - 0x08000000 + 4], "little")}
        def send(self, command):
            raise AssertionError("Capture sent a reset or write command: " + command)
        def disconnect(self):
            pass

    modules = {"reactor": SimpleNamespace(Reactor=Loop), "serialhdl": SimpleNamespace(SerialReader=Reader),
               "serial": SimpleNamespace(Serial=lambda *args, **kwargs: object())}
    with tempfile.TemporaryDirectory(prefix="thr-capture-check-") as temporary, patch.dict(sys.modules, modules):
        directory = Path(temporary) / "capture"
        with patch.object(tool.subprocess, "run", return_value=SimpleNamespace(stdout="inactive", returncode=0)):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = tool.main(["snapshot", "--output-dir", str(directory), "--printer-idle-confirmed"])
        supported = tool.digest(boot) in tool.thr_bootloaders.ADMITTED_BOOTLOADERS
        assert status == (0 if supported else tool.UNSUPPORTED_BOOTLOADER)
        assert len(commands) == len(set(commands)) and addresses
        assert (directory / "bootloader.bin").read_bytes() == boot
        assert (directory / "application.bin").read_bytes() == stock
        summary = json.loads((directory / "report.json").read_text())
        assert summary["bootloader_sha256"] == tool.digest(boot) and "flash" not in summary
        assert len(summary["bootloader_page_sha256"]) == 16
        assert all(path.stat().st_mode & 0o777 == 0o600 for path in directory.iterdir())
        if supported:
            try:
                tool.application_session(manifest, reset=True, expected_boot=boot[:-1])
            except ValueError:
                pass
            else:
                raise AssertionError("Mismatched installed bootloader reset was admitted")
            try:
                tool.verify_readback(stock, directory, manifest, expected_bootloader=boot[:-1])
            except ValueError:
                pass
            else:
                raise AssertionError("Changed bootloader was accepted by readback verification")
        else:
            assert (directory / "application-region.bin").read_bytes() == flash[0x8000:]
            try:
                tool.application_session(manifest, reset=True, expected_boot=boot, capture_root=Path(temporary))
            except ValueError:
                pass
            else:
                raise AssertionError("Unknown bootloader reset was admitted")
            capture, = Path(temporary).glob("unsupported-thr-*")
            assert (capture / "application-region.bin").read_bytes() == flash[0x8000:]


def check_transfer(stock, patched, boot, manifest, profile):
    results = []
    for image in (stock, patched):
        for mode in ("normal", "bad-data", "bad-reply", "lost-ack", "stale-ack"):
            board = NativeBoard(boot, stock) if boot else None
            peer = Peer(mode, board, profile)
            result = tool.Bootloader(peer, profile, peer.clock).transfer(image, manifest)
            assert result["transfer_acknowledged"] and not result["verified"]
            actual = board.application(len(image)) if board else b"".join(peer.pages[index] for index in sorted(peer.pages))
            assert actual == image
            assert len(peer.sent) == (38 if mode == "normal" else 39)
            if board:
                assert board.erases == list(range(*profile.erase_range))
                padded_end = (len(image) + 1023) // 1024 * 1024
                assert board.application(padded_end)[len(image):] == profile.final_padding * (padded_end - len(image))
                assert board.application(0x18000)[padded_end:] == b"\xff" * (0x18000 - padded_end)
            results.append({"image_sha256": tool.digest(image), "mode": mode, "packets": len(peer.sent)})
    for mode in ("first-lost-ack", "first-bad-reply"):
        board = NativeBoard(boot, stock) if boot else None
        peer = Peer(mode, board, profile)
        try:
            tool.Bootloader(peer, profile, peer.clock).transfer(patched, manifest)
        except TimeoutError:
            assert len(peer.sent) == 3
            if board:
                assert len(board.writes) == 256
        else:
            raise AssertionError("Ambiguous packet-zero acknowledgement was retried")
    for mode, expected_packets in (("lost-start-ack", 2), ("lost-end-ack", 38)):
        board = NativeBoard(boot, stock) if boot else None
        peer = Peer(mode, board, profile)
        try:
            tool.Bootloader(peer, profile, peer.clock).transfer(patched, manifest)
        except TimeoutError:
            assert len(peer.sent) == expected_packets
        else:
            raise AssertionError("Incomplete transfer was reported as acknowledged")
    for mode, error in (("wrong-board", ValueError), ("silent", TimeoutError)):
        peer = Peer(mode, profile=profile)
        try:
            tool.Bootloader(peer, profile, peer.clock).transfer(patched, manifest)
        except error:
            assert not peer.erased
        else:
            raise AssertionError("Unsafe bootloader handshake was accepted")
    peer = Peer(board=NativeBoard(boot, stock) if boot else None, profile=profile)
    tool.Bootloader(peer, profile, peer.clock).probe()
    assert not peer.erased and not peer.pages
    if peer.board:
        peer.board.timeout()
        assert peer.board.jumps
        assert peer.board.application(len(stock)) == stock and not peer.board.erases
    return results


def check_interruption(stock, patched, boot, manifest, profile):
    board = NativeBoard(boot, stock)
    assert board.receive(tool.encode(0, b"\x01\x00"))
    assert board.receive(tool.encode(1, b"\x01\x00" + len(patched).to_bytes(4, "big")))
    data = patched[:1024]
    assert board.receive(tool.encode(2, b"\x00\x00\x00\x00\x04\x00" + data))
    partial = board.application(0x18000)
    board.timeout()
    assert board.application(2048) == b"\xff" * 2048
    if profile.reset_hook is not None:
        assert board.resets and not board.jumps
        board = NativeBoard(boot, board.application(0x18000))
    peer = Peer(board=board)
    tool.Bootloader(peer, profile, peer.clock).transfer(stock, manifest)
    assert board.application(len(stock)) == stock
    cold = NativeBoard(boot, partial)
    cold.timeout()
    assert cold.jumps, "Cold startup behavior changed; re-audit recovery assumptions"
    return {"link_timeout_stock_recovery": True, "cold_start_can_jump_to_partial_application": True}


def check_native_protocol(stock, patched, boot, profile):
    board = NativeBoard(boot, stock)
    identity = board.receive(tool.encode(0, b"\x01\x00"))
    assert identity == [tool.encode(0, profile.identity_reply)]
    assert board.receive(tool.encode(1, b"\x01\x00" + len(patched).to_bytes(4, "big")))
    for index in (0, 0, 1, 1):
        before = len(board.writes)
        data = patched[index * 1024:(index + 1) * 1024]
        header = index.to_bytes(4, "big") + len(data).to_bytes(2, "big")
        assert board.receive(tool.encode(2, header + data)) == [tool.encode(2, header + b"\x01")]
        if index == 0:
            assert len(board.writes) - before == 256
        elif before == 512:
            assert len(board.writes) - before == 256
        else:
            assert len(board.writes) == before
    if profile.tick is not None:
        startup = NativeBoard(boot, stock)
        startup.advance(profile.startup_ticks + 999)
        assert not startup.jumps
        startup.advance(1)
        assert startup.jumps and not startup.erases and startup.application(len(stock)) == stock
        probe = NativeBoard(boot, stock)
        assert probe.receive(tool.encode(0, b"\x01\x00")) == identity
        probe.advance(10999)
        assert not probe.jumps
        probe.advance(1)
        assert probe.jumps and not probe.erases and probe.application(len(stock)) == stock
        board.advance(10999)
        assert not board.resets
        board.advance(1)
        assert board.resets and board.application(2048) == b"\xff" * 2048
    return {"identity_reply": profile.identity_reply.hex(), "duplicate_zero_programs_again": True,
            "later_duplicate_does_not_program": True, "startup_and_session_ticks_checked": profile.tick is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-image", required=True, type=Path)
    parser.add_argument("--patched-image", required=True, type=Path)
    parser.add_argument("--bootloader-backup", type=Path, action="append", default=[],
                        help="captured image; repeat to check multiple exact profiles")
    args = parser.parse_args()
    manifest = json.loads(tool.MANIFEST.read_text())
    stock, patched = args.stock_image.read_bytes(), args.patched_image.read_bytes()
    assert tool.admitted_image(stock, manifest) == manifest["thr"]["stock_sha256"]
    assert tool.admitted_image(patched, manifest) == manifest["thr"]["patched_sha256"]
    reports = []
    captures = [(path.read_bytes(), None) for path in args.bootloader_backup]
    for boot, profile in captures or [(None, profile) for profile in PROFILES.values()]:
        profile = identify_bootloader(boot, admitted=False) if boot else profile
        if boot:
            check_admission(stock, patched, boot, manifest, profile)
            check_capture(stock, boot, manifest)
            with patch.object(tool.thr_bootloaders, "ADMITTED_BOOTLOADERS", frozenset()):
                check_capture(stock, boot, manifest)
        else:
            fixture = b"\x00" * 0x8000
            fixture_profile = replace(profile, sha256=tool.digest(fixture))
            admitted = frozenset((fixture_profile.sha256,)) if profile.sha256 in tool.thr_bootloaders.ADMITTED_BOOTLOADERS else frozenset()
            with patch.dict(PROFILES, {fixture_profile.sha256: fixture_profile}), patch.object(tool.thr_bootloaders, "ADMITTED_BOOTLOADERS", admitted):
                check_admission(stock, patched, fixture, manifest, fixture_profile)
                check_capture(stock, fixture, manifest)
                with patch.object(tool.thr_bootloaders, "ADMITTED_BOOTLOADERS", frozenset()):
                    check_capture(stock, fixture, manifest)
        reports.append({"bootloader_sha256": profile.sha256, "native_bootloader": bool(boot),
                        "admitted": profile.sha256 in tool.thr_bootloaders.ADMITTED_BOOTLOADERS,
                        "transfers": check_transfer(stock, patched, boot, manifest, profile)})
        if boot:
            reports[-1]["interruption"] = check_interruption(stock, patched, boot, manifest, profile)
            reports[-1]["protocol"] = check_native_protocol(stock, patched, boot, profile)
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
