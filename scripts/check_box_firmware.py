#!/usr/bin/env python3
"""Offline checks for the QIDI Box shutdown fix and the Box transfer tool.

Always: the patch applies only to the pinned stock image, changes only the
manifest regions, and the patched data dictionary served by `identify` (run in
emulation) differs from stock only in its version.

--bootloader-backup: runs the transfer tool against the captured bootloader's
own code (USB stack, delays, PLL setup, and the final jump or reset stubbed;
flash controller modelled at register level): stock and patched transfers,
lost acknowledgements, an unacknowledged packet 0, a non-erasing probe, and a
resident bootloader.

--ram-dump: runs the application's shutdown handlers from a configured Box's
RAM (read with debug_read): stock must re-enter shutdown(), patched must reach
the shutdown report with the original reason.

Requires firmware/check-requirements.txt. No binaries are shipped; pass your own.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_MCLASS, UC_MODE_THUMB, Uc, UcError
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flash_box_firmware as tool  # noqa: E402
from build_box_firmware import load_manifest, patch_box  # noqa: E402

BASE = 0x08008000
# Application (stock 02.03.01.21) addresses.
IDENTIFY, SENDF = 0x08009524, 0x080083A4
SHUTDOWN_HANDLERS, SHUTDOWN, SHUTDOWN_REPORT = 0x08009048, 0x0800831C, 0x08009392
DICTIONARY, DICTIONARY_BYTES = 0x080103F8, 3156
# Recovered hooks for the admitted bootloader build.
BOOTLOADER_HOOKS = {
    "64962da860449bd3af7ead7cc194ec01192493b0b3e7eedc70e384f61bf7b1e4": dict(
        reset=0x080049DC, main_loop=0x08004494, main_entry=0x080049D0, systick=0x0800363C, cdc_rx=0x08003774,
        tx=0x08003820, jump=0x08003C78, system_reset=0x08003CE4, error=0x08004810,
        stubs=(0x080045EC, 0x08003684, 0x08000AFC, 0x080029B2, 0x08002A00, 0x08002A66)),
    # COLOR_BOOT build: no NVIC reset path; leaves the rest of the last page erased.
    "1e00811df777a8cf21098b1386319a440c90e04aa2a9ab0aeef11dc810891b1e": dict(
        reset=0x08004AB4, main_loop=0x08004584, main_entry=0x08004AAC, systick=0x080035C0, cdc_rx=0x080036F8,
        tx=0x08003784, jump=0x08003BDC, system_reset=None, error=0x080048E0, fill=0xFF,
        stubs=(0x080046BC, 0x08003608, 0x08000A80, 0x08002936, 0x08002984, 0x080029EA)),
}
SECTORS = [(0x08000000, 0x4000), (0x08004000, 0x4000), (0x08008000, 0x4000), (0x0800C000, 0x4000),
           (0x08010000, 0x10000), (0x08020000, 0x20000)]
FLASH_CR = 0x40023C10
SENTINEL = 0x2000F001


class CheckFailed(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


# ---- application image -----------------------------------------------------

def emulate_identify(image: bytes) -> bytes:
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.mem_map(0x08000000, 0x40000)
    mu.mem_write(BASE, image)
    mu.mem_map(0x20000000, 0x10000)
    captured = []

    def hook(uc, address, size, user):
        captured.append((uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2), uc.reg_read(UC_ARM_REG_R3)))
        uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook, begin=SENDF, end=SENDF + 1)
    data = b""
    while True:
        mu.mem_write(0x20001000, struct.pack("<II", len(data), 40))
        mu.reg_write(UC_ARM_REG_R0, 0x20001000)
        mu.reg_write(UC_ARM_REG_SP, 0x2000F000)
        mu.reg_write(UC_ARM_REG_LR, 0x08000001)
        captured.clear()
        mu.emu_start(IDENTIFY | 1, 0x08000000, count=200)
        require(len(captured) == 1, "identify did not send a response")
        offset, count, pointer = captured[0]
        require(offset == len(data), "identify answered the wrong offset")
        chunk = bytes(mu.mem_read(pointer, count)) if count else b""
        data += chunk
        if len(chunk) < 40:
            return data


def check_image(stock: bytes, manifest: dict) -> bytes:
    box = manifest["box"]
    require(tool.image_identity(stock, manifest) == "stock", "stock image is not the pinned 02.03.01.21 image")
    patched = patch_box(stock, manifest)
    require(tool.image_identity(patched, manifest) == "patched", "patched image hash differs from the manifest")
    for bad in (patched, stock[:-1], stock[:-1] + bytes([stock[-1] ^ 1])):
        try:
            patch_box(bad, manifest)
        except ValueError:
            continue
        raise CheckFailed("patch accepted an image that is not the pinned stock image")
    allowed = set()
    for patch in box["patches"]:
        offset = int(patch["offset"], 0)
        allowed.update(range(offset, offset + len(bytes.fromhex(patch["after"]))))
    require(all(i in allowed for i in range(len(stock)) if stock[i] != patched[i]), "bytes changed outside the manifest")
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    expected = {0x080090B6: ("b", "#0x80090ec"), 0x08009528: ("movw", "r3, #0xc04"),
                0x08009534: ("movw", "r3, #0xc05"), 0x0800953C: ("rsb.w", "r2, r1, #5")}
    for address, (mnemonic, operands) in expected.items():
        instruction = next(disassembler.disasm(patched[address - BASE:address - BASE + 4], address))
        require((instruction.mnemonic, instruction.op_str) == (mnemonic, operands), f"unexpected instruction at {address:#x}")
    stock_dictionary = json.loads(zlib.decompress(emulate_identify(stock)))
    patched_dictionary = json.loads(zlib.decompress(emulate_identify(patched)))
    require(stock_dictionary["version"] == box["stock_version"], "stock dictionary version")
    require(patched_dictionary["version"] == box["patched_version"], "patched dictionary version")
    patched_dictionary["version"] = stock_dictionary["version"]
    require(patched_dictionary == stock_dictionary, "patched dictionary differs beyond the version")
    print("image: patch, changed regions, instructions, and identify dictionary OK")
    return patched


# ---- bootloader emulation --------------------------------------------------

class Board:
    def __init__(self, boot: bytes, app_region: bytes):
        self.hooks = BOOTLOADER_HOOKS[tool.digest(boot)]
        self.boot = boot
        self.uc = uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        for base, size in ((0x08000000, 0x40000), (0x1FFF0000, 0x10000), (0x20000000, 0x10000),
                           (0x40000000, 0x30000), (0x50000000, 0x40000), (0xE0000000, 0x100000)):
            uc.mem_map(base, size)
        uc.mem_write(0x08000000, boot)
        uc.mem_write(BASE, b"\xff" * 0x38000)
        uc.mem_write(BASE, app_region)
        uc.mem_write(FLASH_CR, struct.pack("<I", 0x80000000))
        self.sent, self.erases, self.bad, self.keys = [], [], [], []
        self.halted, self.ms, self.pending = None, 0, None
        uc.hook_add(UC_HOOK_CODE, self._code)
        uc.hook_add(UC_HOOK_MEM_WRITE, self._flash_write, begin=0x08000000, end=0x0803FFFF)
        uc.hook_add(UC_HOOK_MEM_WRITE, self._controller, begin=0x40023C00, end=0x40023C1F)
        uc.reg_write(UC_ARM_REG_SP, 0x20010000)
        self._run(self.hooks["reset"] | 1, self.hooks["main_entry"])
        self.main_sp = uc.reg_read(UC_ARM_REG_SP)
        # Frames sent before USB enumeration never reach the host.
        self.sent.clear()

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
            self._return()
        elif address == hooks["tx"]:
            self.sent.append(bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1))))
            self._return()
        elif address in (hooks["jump"], hooks["system_reset"], hooks["error"]):
            self.halted = {hooks["jump"]: "jump", hooks["system_reset"]: "system_reset", hooks["error"]: "error"}[address]
            uc.emu_stop()

    def _controller(self, uc, access, address, size, value, user):
        if address == 0x40023C04:
            self.keys.append(value)
            if self.keys[-2:] == [0x45670123, 0xCDEF89AB]:
                control = struct.unpack("<I", uc.mem_read(FLASH_CR, 4))[0]
                uc.mem_write(FLASH_CR, struct.pack("<I", control & 0x7FFFFFFF))
        elif address == FLASH_CR and value & (1 << 16) and value & 2:
            sector = (value >> 3) & 0xF
            self.erases.append(sector)
            if sector < len(SECTORS):
                start, length = SECTORS[sector]
                uc.mem_write(start, b"\xff" * length)
            self.pending = (FLASH_CR, value & ~(1 << 16))

    def _flash_write(self, uc, access, address, size, value, user):
        control = struct.unpack("<I", uc.mem_read(FLASH_CR, 4))[0]
        if not control & 1 or control & 0x80000000 or address < BASE:
            self.bad.append(hex(address))
        previous = struct.unpack("<I", uc.mem_read(address & ~3, 4))[0]
        if size == 4:
            if previous & value != value:
                self.bad.append(hex(address))
            self.pending = (address, previous & value)

    def _run(self, start, until):
        try:
            self.uc.emu_start(start, until, count=20_000_000)
        except UcError as error:
            self.halted = "fault " + str(error)
        if self.pending:
            target, value = self.pending
            self.pending = None
            self.uc.mem_write(target, struct.pack("<I", value))

    def call(self, function, *arguments):
        if self.halted:
            return
        self.uc.reg_write(UC_ARM_REG_SP, self.main_sp)
        self.uc.reg_write(UC_ARM_REG_LR, SENTINEL)
        for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1), arguments):
            self.uc.reg_write(register, value)
        self._run(function | 1, SENTINEL & ~1)

    def tick(self, milliseconds=1):
        for _ in range(milliseconds):
            if self.halted:
                return
            self.ms += 1
            self.call(self.hooks["systick"])
            self.call(self.hooks["main_loop"])
            self.call(self.hooks["main_loop"])

    def usb_out(self, raw: bytes):
        # A transfer that ends on a packet boundary is closed by a zero-length packet.
        for offset in range(0, len(raw) + (0 if len(raw) % 64 else 1), 64):
            chunk = raw[offset:offset + 64]
            self.uc.mem_write(0x2000E000, chunk.ljust(64, b"\0"))
            self.uc.mem_write(0x2000E100, struct.pack("<I", len(chunk)))
            self.call(self.hooks["cdc_rx"], 0x2000E000, 0x2000E100)
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
    fill = BOOTLOADER_HOOKS[tool.digest(boot)].get("fill", 0)
    installed = stock + bytes([fill]) * (padded - len(stock))

    def board(app_region=installed):
        b = Board(boot, app_region)
        b.tick(600)
        return b

    def written(b, image):
        region = b.flash(BASE, 0x18000)
        return region[:len(image)] == image and set(region[len(image):padded]) == {fill} and set(region[padded:]) == {0xFF}

    cases = (("stock", stock, (), installed), ("patched", patched, (), installed),
             ("patched, lost ack on packet 5", patched, (("data", 5),), installed),
             ("patched, lost ack on last packet", patched, (("data", padded // 1024 - 1),), installed),
             ("patched, bootloader resident", patched, (), b"\xff" * 0x1000))
    for name, image, drop, region in cases:
        b = board(region)
        result = tool.Bootloader(EmulatedPort(b, drop), profile, clock=lambda b=b: b.ms / 1000).transfer(image, manifest)
        b.tick(3000)
        require(result["transfer_acknowledged"] and written(b, image), f"{name}: flash differs from the image")
        require(b.flash(0x08000000, 0x8000) == boot and not b.bad, f"{name}: bootloader or unerased write")
        require(b.halted == "jump", f"{name}: application not started")
        print(f"transfer: {name} OK")

    b = board()
    try:
        tool.Bootloader(EmulatedPort(b, (("data", 0),)), profile, clock=lambda: b.ms / 1000).transfer(patched, manifest)
        raise CheckFailed("packet 0 failure was not reported")
    except tool.TransferFailed:
        pass
    b.tick(12000)  # the slower build gives up on a session after 10 s
    require(set(b.flash(BASE, 0x1000)) == {0xFF} and b.flash(0x08000000, 0x8000) == boot,
            "packet 0 failure: first application sector not blank or bootloader changed")
    print("transfer: unacknowledged packet 0 leaves the bootloader resident OK")

    b = board()
    reply = tool.Bootloader(EmulatedPort(b), profile, clock=lambda: b.ms / 1000).probe()
    b.tick(12000)  # the slower build gives up on a session after 10 s
    require(reply == bytes.fromhex(profile["identity_reply"]) and not b.erases and b.halted == "jump"
            and b.flash(BASE, len(installed)) == installed, "probe erased or did not return to the application")
    print("transfer: non-erasing probe returns to the application OK")


def check_shutdown(boot: bytes, ram: bytes, stock: bytes, patched: bytes) -> None:
    for name, image, expect_report in (("stock", stock, False), ("patched", patched, True)):
        for reason in (0x0A, 0x1C, 0x20):
            mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
            for base in (0x00000000, 0x08000000):
                mu.mem_map(base, 0x40000)
                mu.mem_write(base, boot)
                mu.mem_write(base + 0x8000, image)
            mu.mem_map(0x20000000, 0x10000)
            mu.mem_write(0x20000000, ram)
            for base, size in ((0x40000000, 0x80000), (0x50000000, 0x40000), (0xE0000000, 0x100000)):
                mu.mem_map(base, size)
            outcome = {}

            def hook(uc, address, size, user, outcome=outcome):
                if address == SHUTDOWN:
                    outcome["reentered"] = uc.reg_read(UC_ARM_REG_R0)
                    uc.emu_stop()
                elif address == SHUTDOWN_REPORT:
                    outcome["reported"] = uc.reg_read(UC_ARM_REG_R2)
                    uc.emu_stop()

            mu.hook_add(UC_HOOK_CODE, hook)
            mu.reg_write(UC_ARM_REG_SP, 0x2000FC00)
            mu.reg_write(UC_ARM_REG_R0, reason)
            mu.emu_start(SHUTDOWN_HANDLERS | 1, 0xFFFFFFFF, count=5_000_000)
            if expect_report:
                require(outcome.get("reported") == reason, f"patched shutdown reason {reason} not reported: {outcome}")
            else:
                require("reentered" in outcome, f"stock shutdown reason {reason} did not reproduce the fault: {outcome}")
        print(f"shutdown: {name} {'reports the original reason' if expect_report else 're-enters shutdown()'} OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stock-image", type=Path, required=True)
    parser.add_argument("--bootloader-backup", type=Path)
    parser.add_argument("--ram-dump", type=Path, help="64 KiB RAM read from a configured Box; needs --bootloader-backup")
    args = parser.parse_args()
    if args.ram_dump and not args.bootloader_backup:
        parser.error("--ram-dump needs --bootloader-backup")
    try:
        manifest = load_manifest()
        stock = args.stock_image.read_bytes()
        patched = check_image(stock, manifest)
        if args.bootloader_backup:
            boot = args.bootloader_backup.read_bytes()
            require(tool.digest(boot) in BOOTLOADER_HOOKS, "bootloader backup is not an admitted build")
            check_transfers(boot, stock, patched, manifest)
            if args.ram_dump:
                check_shutdown(boot, args.ram_dump.read_bytes(), stock, patched)
    except CheckFailed as failure:
        print(f"Box firmware check failed: {failure}", file=sys.stderr)
        return 1
    print("Box firmware checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
