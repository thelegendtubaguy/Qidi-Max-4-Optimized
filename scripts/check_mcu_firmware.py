#!/usr/bin/env python3
"""Offline checks for the Max 4 mainboard closed-loop reply fix.

Always: the patch applies only to the pinned stock image and changes only the
manifest regions; the data dictionary served by `identify` (run in emulation)
differs from stock only in its version; and the firmware's own closed-loop
reply parser and idle-timeout check, run in emulation on stock and patched
images, show that:

- every reply in the manifest's length table reaches the host on its last
  byte, where stock holds all but 0x37 and 0x40 for 50 ms of bus silence;
- back-to-back replies and a corrupted reply followed by a good one parse;
- replies of every other function code, and randomized streams of them with
  noise and gaps, reach the host exactly as they do on stock.

--bootloader-backup: runs the transfer tool against the captured mainboard
bootloader's own code (clock, GPIO, and USB core stubbed; CDC packets injected
into its class buffer; the GD32 flash controller's page erase modelled at
register level): stock and patched transfers, lost acknowledgements, a
resident bootloader, an unacknowledged packet 0, and a non-erasing probe.

Requires firmware/check-requirements.txt. No binaries are shipped; pass your own.
"""
from __future__ import annotations

import argparse
import json
import random
import struct
import sys
import zlib
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_MCLASS, UC_MODE_THUMB, Uc, UcError
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flash_box_firmware as tool  # noqa: E402
from build_mcu_firmware import load_manifest, patch_mcu  # noqa: E402
from flash_box_firmware import digest  # noqa: E402

BASE = 0x08008000
# Application (stock 02.01.01.12) addresses.
IDENTIFY, SENDF = 0x08008A64, 0x080085DC
REPLY_LENGTH = 0x0800DB0C
CL_PARSE_BYTE, CL_IDLE_CHECK = 0x0800E460, 0x0800E708
TICKS_PER_US = 168
BYTE_US = 260  # one 8N1 character at 38400 baud
IDLE_TIMEOUT_US = 50_000
SENTINEL = 0x08000001
# Recovered hooks for the admitted DRIVER BOOT bootloader build.
BOOTLOADER_HOOKS = {
    "60be62899f94afb00dc733baf3620f6a1a48ca7d210e477875cbe123139cbec4": dict(
        reset=0x0800350C, main_entry=0x08003504, main_loop=0x080032BC, systick=0x0800242C,
        tx=0x080027BC, jump=0x08002954,
        error=(0x0800241A, 0x0800241C, 0x0800241E, 0x08002420, 0x08002422, 0x08003446, 0x08003470, 0x0800355C),
        # SystemInit, clocks, GPIO, delay, USB core init, CDC sent (returns 1), CDC re-arm, USB deinit.
        stubs=(0x080002C0, 0x080033F4, 0x080026CC, 0x080003EC, 0x0800283C, 0x08000DEC, 0x08000E28, 0x080028B0),
        sent_check=0x08000DEC, device=0x200003F8),
}
FLASH_END = 0x08080000
PAGE = 0x1000
FMC = 0x40023C00
FMC_KEY, FMC_STAT, FMC_CTL, FMC_PECFG = FMC + 0x04, FMC + 0x0C, FMC + 0x10, FMC + 0x20
CDC = 0x20020000
BOOT_SENTINEL = 0x2003F001


class CheckFailed(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def frame(address: int, function: int, payload: bytes) -> bytes:
    body = bytes([0xFB, address, function]) + payload
    return body + bytes([sum(body) & 0xFF])


# ---- application image -----------------------------------------------------

def _machine(image: bytes) -> Uc:
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.mem_map(0x08000000, 0x100000)
    mu.mem_write(BASE, image)
    mu.mem_map(0x20000000, 0x20000)
    return mu


def emulate_identify(image: bytes) -> bytes:
    mu = _machine(image)
    captured = []

    def hook(uc, address, size, user):
        captured.append((uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2), uc.reg_read(UC_ARM_REG_R3)))
        uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook, begin=SENDF, end=SENDF + 1)
    data = b""
    while True:
        mu.mem_write(0x20001000, struct.pack("<II", len(data), 40))
        mu.reg_write(UC_ARM_REG_R0, 0x20001000)
        mu.reg_write(UC_ARM_REG_SP, 0x2001F000)
        mu.reg_write(UC_ARM_REG_LR, SENTINEL)
        captured.clear()
        mu.emu_start(IDENTIFY | 1, SENTINEL & ~1, count=200)
        require(len(captured) == 1, "identify did not send a response")
        offset, count, pointer = captured[0]
        require(offset == len(data), "identify answered the wrong offset")
        chunk = bytes(mu.mem_read(pointer, count)) if count else b""
        data += chunk
        if len(chunk) < 40:
            return data


def check_image(stock: bytes, manifest: dict) -> bytes:
    mcu = manifest["mcu"]
    require(digest(stock) == mcu["stock_sha256"] and len(stock) == mcu["size"], "stock image is not the pinned 02.01.01.12 image")
    patched = patch_mcu(stock, manifest)
    require(digest(patched) == mcu["patched_sha256"], "patched image hash differs from the manifest")
    for bad in (patched, stock[:-1], stock[:-1] + bytes([stock[-1] ^ 1])):
        try:
            patch_mcu(bad, manifest)
        except ValueError:
            continue
        raise CheckFailed("patch accepted an image that is not the pinned stock image")
    allowed = set()
    for patch in mcu["patches"]:
        offset = int(patch["offset"], 0)
        allowed.update(range(offset, offset + len(bytes.fromhex(patch["after"]))))
    require(all(i in allowed for i in range(len(stock)) if stock[i] != patched[i]), "bytes changed outside the manifest")
    stub = next(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(patched[REPLY_LENGTH - BASE:REPLY_LENGTH - BASE + 4], REPLY_LENGTH))
    require(stub.mnemonic == "b.w", "reply-length function does not branch to the table")
    stock_dictionary = json.loads(zlib.decompress(emulate_identify(stock)))
    patched_dictionary = json.loads(zlib.decompress(emulate_identify(patched)))
    require(stock_dictionary["version"] == mcu["stock_version"], "stock dictionary version")
    require(patched_dictionary["version"] == mcu["patched_version"], "patched dictionary version")
    patched_dictionary["version"] = stock_dictionary["version"]
    require(patched_dictionary == stock_dictionary, "patched dictionary differs beyond the version")
    print("image: patch, changed regions, branch, and identify dictionary OK")
    return patched


# ---- closed-loop reply parser ----------------------------------------------

class Parser:
    """The mainboard's cl task: each run checks the idle timeout, then parses
    the bytes drained from the UART ring, as the task at 0x0800e928 does."""

    def __init__(self, image: bytes):
        self.uc = uc = _machine(image)
        self.replies: list[tuple[int, bytes]] = []
        self.now = 1_000_000
        uc.hook_add(UC_HOOK_CODE, self._sendf, begin=SENDF, end=SENDF + 1)

    def _sendf(self, uc, address, size, user):
        length, pointer = uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2)
        self.replies.append((self.now, bytes(uc.mem_read(pointer, length))))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def _call(self, function: int, *arguments: int) -> None:
        for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1), arguments):
            self.uc.reg_write(register, value)
        self.uc.reg_write(UC_ARM_REG_SP, 0x2001F000)
        self.uc.reg_write(UC_ARM_REG_LR, SENTINEL)
        self.uc.emu_start(function | 1, SENTINEL & ~1, count=100_000)

    def task(self, data: bytes = b"") -> None:
        clock = (self.now * TICKS_PER_US) & 0xFFFFFFFF
        self._call(CL_IDLE_CHECK, clock)
        for byte in data:
            self._call(CL_PARSE_BYTE, byte, clock)

    def receive(self, data: bytes, *, batched: bool = False) -> None:
        """Bytes arrive one character time apart; the task runs per byte, or once at the end."""
        if batched:
            self.now += BYTE_US * len(data)
            self.task(data)
            return
        for byte in data:
            self.now += BYTE_US
            self.task(bytes([byte]))

    def idle(self, microseconds: int, step: int = 1000) -> None:
        end = self.now + microseconds
        while self.now < end:
            self.now = min(end, self.now + step)
            self.task()


def run_stream(image: bytes, events) -> list[tuple[int, bytes]]:
    parser = Parser(image)
    for kind, value in events:
        if kind == "bytes":
            parser.receive(value)
        else:
            parser.idle(value)
    parser.idle(IDLE_TIMEOUT_US * 2)
    return parser.replies


def check_parser(stock: bytes, patched: bytes, manifest: dict) -> None:
    lengths = {int(code, 0): length for code, length in manifest["mcu"]["reply_lengths"].items()}
    rng = random.Random(20261107)
    for code, length in sorted(lengths.items()):
        reply = frame(1, code, bytes(rng.randrange(256) for _ in range(length - 4)))
        for batched in (False, True):
            outcome = {}
            for name, image in (("stock", stock), ("patched", patched)):
                parser = Parser(image)
                parser.receive(reply, batched=batched)
                done = parser.now
                parser.idle(IDLE_TIMEOUT_US * 2)
                outcome[name] = [(at - done, data) for at, data in parser.replies]
            require(outcome["patched"] == [(0, reply)], f"{code:#04x}: patched did not deliver the reply on its last byte")
            if code in (0x37, 0x40):
                require(outcome["stock"] == [(0, reply)], f"{code:#04x}: stock reference changed")
            else:
                require(len(outcome["stock"]) == 1 and outcome["stock"][0][1] == reply
                        and outcome["stock"][0][0] >= IDLE_TIMEOUT_US, f"{code:#04x}: stock reference did not wait for the idle timeout")
    print("parser: " + ", ".join(f"{code:#04x}" for code in sorted(lengths)) + " delivered on the last byte (stock waits 50 ms) OK")

    position_error, encoder, temperature = frame(1, 0x39, bytes(4)), frame(3, 0x31, bytes(range(6))), frame(3, 0x3B, b"\x0b\x90")
    parser = Parser(patched)
    parser.receive(position_error + encoder + temperature)
    require([data for _, data in parser.replies] == [position_error, encoder, temperature], "back-to-back replies were not all delivered")
    corrupt = position_error[:-1] + bytes([position_error[-1] ^ 1])
    for batched in (False, True):
        parser = Parser(patched)
        parser.receive(corrupt, batched=batched)
        parser.receive(encoder, batched=batched)
        require([data for _, data in parser.replies] == [encoder], "a corrupted reply affected the next one")
    print("parser: back-to-back replies and a corrupted reply followed by a good one OK")

    unlisted = [code for code in range(256) if code not in lengths and code != 0xFB]
    sizes = {0x47: 38, 0x48: 24, 0x4A: 9, 0x43: 6, 0x42: 8, 0x30: 10, 0x38: 14, 0xF0: 13, 0xF2: 12, 0xF9: 20, 0x80: 5, 0x91: 5}
    for code in unlisted:
        reply = frame(1, code, bytes(rng.randrange(256) for _ in range(sizes.get(code, 5) - 4)))
        events = [("bytes", reply)]
        require(run_stream(stock, events) == run_stream(patched, events), f"{code:#04x}: unlisted reply differs from stock")
    for _ in range(40):
        events = []
        for _ in range(rng.randrange(1, 5)):
            code = rng.choice(unlisted)
            body = frame(rng.choice((1, 3)), code, bytes(rng.randrange(256) for _ in range(sizes.get(code, 5) - 4)))
            if rng.random() < 0.3:
                body = bytes(rng.choice([b for b in range(256) if b != 0xFB]) for _ in range(rng.randrange(1, 4))) + body
            if rng.random() < 0.2:
                body = body[:-1] + bytes([body[-1] ^ 0x5A])
            events += [("bytes", body), ("idle", rng.choice((300, 5_000, 30_000, 60_000)))]
        require(run_stream(stock, events) == run_stream(patched, events), "a randomized unlisted stream differs from stock")
    print(f"parser: {len(unlisted)} unlisted function codes and 40 randomized streams match stock OK")


# ---- bootloader emulation --------------------------------------------------

class Board:
    def __init__(self, boot: bytes, app_region: bytes):
        self.hooks = hooks = BOOTLOADER_HOOKS[digest(boot)]
        self.uc = uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        for base, size in ((0x08000000, 0x80000), (0x1FFF0000, 0x10000), (0x20000000, 0x40000),
                           (0x40000000, 0x30000), (0x50000000, 0x40000), (0xE0000000, 0x100000)):
            uc.mem_map(base, size)
        uc.mem_write(0x08000000, boot)
        uc.mem_write(BASE, b"\xff" * (FLASH_END - BASE))
        uc.mem_write(BASE, app_region)
        uc.mem_write(FMC_CTL, struct.pack("<I", 0x80000000))
        self.sent, self.erases, self.bad, self.keys = [], [], [], []
        self.halted, self.ms, self.pending = None, 0, None
        uc.hook_add(UC_HOOK_CODE, self._code)
        uc.hook_add(UC_HOOK_MEM_WRITE, self._flash_write, begin=0x08000000, end=FLASH_END - 1)
        uc.hook_add(UC_HOOK_MEM_WRITE, self._controller, begin=FMC, end=FMC + 0x2F)
        uc.reg_write(UC_ARM_REG_SP, 0x20030000)
        self._run(hooks["reset"] | 1, hooks["main_entry"])
        require(self.halted is None, f"bootloader startup halted: {self.halted}")
        self.main_sp = uc.reg_read(UC_ARM_REG_SP)
        # USB configured, with the CDC class data in scratch RAM.
        uc.mem_write(hooks["device"] + 0x430, struct.pack("<I", CDC))
        uc.mem_write(hooks["device"] + 0xCE, b"\x03")
        self.sent.clear()

    def _reg(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def _return(self, value=0):
        self.uc.reg_write(UC_ARM_REG_R0, value)
        self.uc.reg_write(UC_ARM_REG_PC, self.uc.reg_read(UC_ARM_REG_LR))

    def _code(self, uc, address, size, user):
        if self.pending:
            target, value = self.pending
            self.pending = None
            uc.mem_write(target, struct.pack("<I", value))
        hooks = self.hooks
        if address in hooks["stubs"]:
            self._return(1 if address == hooks["sent_check"] else 0)
        elif address == hooks["tx"]:
            self.sent.append(bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1))))
            self._return()
        elif address == hooks["jump"] or address in hooks["error"]:
            self.halted = "jump" if address == hooks["jump"] else f"error at {address:#x}"
            uc.emu_stop()

    def _controller(self, uc, access, address, size, value, user):
        if address == FMC_STAT:
            self.pending = (FMC_STAT, self._reg(FMC_STAT) & ~value)  # write 1 to clear
        elif address == FMC_KEY:
            self.keys.append(value)
            if self.keys[-2:] == [0x45670123, 0xCDEF89AB]:
                uc.mem_write(FMC_CTL, struct.pack("<I", self._reg(FMC_CTL) & 0x7FFFFFFF))
        elif address == FMC_CTL and value & (1 << 16) and value & 2:
            pecfg = self._reg(FMC_PECFG)
            if self._reg(FMC_CTL) & 0x80000000 or not pecfg & 0x80000000:
                self.bad.append(f"locked or sector erase {value:#x}")
            else:
                page = (pecfg & 0x0FFFFFFF | 0x08000000) & ~(PAGE - 1)
                self.erases.append(page)
                if page < BASE:
                    self.bad.append(f"erase {page:#x}")
                uc.mem_write(page, b"\xff" * PAGE)
            self.pending = (FMC_CTL, value & ~(1 << 16))

    def _flash_write(self, uc, access, address, size, value, user):
        control = self._reg(FMC_CTL)
        if not control & 1 or control & 0x80000000 or address < BASE or size != 4:
            self.bad.append(f"write {address:#x}")
        previous = struct.unpack("<I", uc.mem_read(address & ~3, 4))[0]
        if previous & value != value:
            self.bad.append(f"unerased write {address:#x}")
        self.pending = (address, previous & value)

    def _run(self, start, until):
        try:
            self.uc.emu_start(start, until, count=50_000_000)
        except UcError as error:
            self.halted = "fault " + str(error)
        if self.pending:
            target, value = self.pending
            self.pending = None
            self.uc.mem_write(target, struct.pack("<I", value))

    def call(self, function):
        if self.halted:
            return
        self.uc.reg_write(UC_ARM_REG_SP, self.main_sp)
        self.uc.reg_write(UC_ARM_REG_LR, BOOT_SENTINEL)
        self._run(function | 1, BOOT_SENTINEL & ~1)

    def tick(self, milliseconds=1):
        for _ in range(milliseconds):
            self.ms += 1
            self.call(self.hooks["systick"])
            self.call(self.hooks["main_loop"])
            self.call(self.hooks["main_loop"])

    def usb_out(self, raw: bytes):
        for offset in range(0, len(raw), 64):
            chunk = raw[offset:offset + 64]
            self.uc.mem_write(CDC, chunk.ljust(64, b"\0"))
            self.uc.mem_write(CDC + 0x4C, struct.pack("<I", len(chunk)))
            self.call(self.hooks["main_loop"])
        self.call(self.hooks["main_loop"])

    def flash(self, address, length):
        return bytes(self.uc.mem_read(address, length))


class EmulatedPort:
    def __init__(self, board: Board, drop=()):
        self.board, self.output, self.seen, self.drop = board, bytearray(), 0, set(drop)

    def _collect(self):
        for raw in self.board.sent[self.seen:]:
            key = ("data", int.from_bytes(raw[4:8], "big")) if raw[1] == 2 else ("kind", raw[1])
            if key in self.drop:
                self.drop.discard(key)
                continue
            self.output.extend(raw)
        self.seen = len(self.board.sent)

    def write(self, raw):
        self.board.usb_out(raw)
        self._collect()
        return len(raw)

    def flush(self):
        pass

    def read(self, count):
        if not self.output:
            self.board.tick(5)
            self._collect()
        chunk = bytes(self.output[:count])
        del self.output[:count]
        return chunk


def check_transfers(boot: bytes, stock: bytes, patched: bytes, manifest: dict) -> None:
    profile = tool.bootloader_profile(boot, manifest)
    padded = (len(stock) + 1023) // 1024 * 1024
    installed = stock + b"\xff" * (padded - len(stock))

    def board(app_region=installed):
        b = Board(boot, app_region)
        b.tick(600)
        return b

    def client(b, drop=()):
        return tool.Bootloader(EmulatedPort(b, drop), profile, clock=lambda: b.ms / 1000)

    def intact(b):
        return b.flash(0x08000000, 0x8000) == boot and not b.bad

    cases = (("stock", stock, (), installed), ("patched", patched, (), installed),
             ("patched, lost ack on packet 5", patched, (("data", 5),), installed),
             ("patched, lost ack on last packet", patched, (("data", padded // 1024 - 1),), installed),
             ("patched, bootloader resident", patched, (), b"\xff" * PAGE))
    for name, image, drop, region in cases:
        b = board(region)
        result = client(b, drop).transfer(image, manifest)
        b.tick(3000)
        require(result["transfer_acknowledged"] and b.flash(BASE, FLASH_END - BASE) == image + b"\xff" * (FLASH_END - BASE - len(image)),
                f"{name}: flash differs from the image")
        require(intact(b) and b.halted == "jump", f"{name}: bootloader changed, bad write, or application not started")
        print(f"transfer: {name} OK")

    b = board()
    try:
        client(b, (("data", 0),)).transfer(patched, manifest)
        raise CheckFailed("packet 0 failure was not reported")
    except tool.TransferFailed:
        pass
    b.tick(27000)
    require(set(b.flash(BASE, PAGE)) == {0xFF} and intact(b) and b.halted is None,
            "packet 0 failure: first application page not blank, bootloader changed, or bootloader left")
    print("transfer: unacknowledged packet 0 leaves the bootloader resident OK")

    b = board()
    reply = client(b).probe()
    b.tick(12000)  # the session expires after 10 s, then the bootloader jumps 1 s later
    require(reply == bytes.fromhex(profile["identity_reply"]) and not b.erases and b.halted == "jump"
            and b.flash(BASE, len(installed)) == installed, "probe erased or did not return to the application")
    print("transfer: non-erasing probe returns to the application OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stock-image", type=Path, required=True)
    parser.add_argument("--bootloader-backup", type=Path)
    args = parser.parse_args()
    try:
        manifest = load_manifest()
        stock = args.stock_image.read_bytes()
        patched = check_image(stock, manifest)
        check_parser(stock, patched, manifest)
        if args.bootloader_backup:
            boot = args.bootloader_backup.read_bytes()
            require(digest(boot) in BOOTLOADER_HOOKS, "bootloader backup is not an admitted build")
            check_transfers(boot, stock, patched, manifest)
    except CheckFailed as failure:
        print(f"Mainboard firmware check failed: {failure}", file=sys.stderr)
        return 1
    print("Mainboard firmware checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
