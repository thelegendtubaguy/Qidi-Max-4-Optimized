#!/usr/bin/env python3
"""Check timed THR transfer recovery against a captured bootloader."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import check_thr_flashing as native
import flash_thr_firmware as tool
from thr_bootloaders import identify_bootloader

UART_SECONDS_PER_BYTE = 10 / 115200
TRIGGERS = ("start", 0, 1, 17, 34, "end")
DURATIONS = (0.5, 3, 6, 9.5, 10.5, 12, 14, 15.5, 17, 25, 40)


class TimedLink:
    def __init__(self, boot, stock, patched, fault=None):
        self.boot, self.stock, self.patched = boot, stock, patched
        self.board = native.NativeBoard(boot, stock)
        self.now = 0.0
        self.ticks = 0
        self.state = "bootloader"
        self.queue = bytearray()
        self.fault = fault
        self.window = None
        self.resets = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.advance(seconds)

    def advance(self, seconds):
        self.now += seconds
        target = int(self.now * 1000)
        while self.ticks < target and self.state == "bootloader":
            self.board.advance(1)
            self.ticks += 1
            self.settle()
        self.ticks = max(self.ticks, target)

    def settle(self):
        if self.board.resets:
            self.resets.append(self.now)
            self.board = native.NativeBoard(self.boot, self.board.application(0x18000))
        elif self.board.jumps:
            app = self.board.application(len(self.stock))
            self.state = "stock" if app == self.stock else "patched" if app == self.patched else "bricked"

    def dropping(self, direction):
        if not self.window or not self.window[1] <= self.now < self.window[2]:
            return False
        return self.window[0] == "dead" or direction == "rx"

    def write(self, raw):
        if self.fault and not self.window:
            mode, trigger, duration = self.fault
            kind, payload = raw[1], raw[4:-2]
            if ((trigger == "start" and kind == 1 and len(payload) == 6)
                    or (trigger == "end" and kind == 1 and len(payload) == 2)
                    or (isinstance(trigger, int) and kind == 2 and int.from_bytes(payload[:4], "big") == trigger)):
                self.window = (mode, self.now, self.now + duration)
        self.advance(len(raw) * UART_SECONDS_PER_BYTE)
        if self.state == "bootloader" and not self.dropping("tx"):
            replies = self.board.receive(raw)
            self.settle()
            if not self.dropping("rx"):
                self.queue.extend(b"".join(replies))
        return len(raw)

    def flush(self):
        pass

    def read(self, count):
        self.advance(0.002)
        chunk = bytes(self.queue[:count])
        del self.queue[:count]
        return chunk


def run(recovering, boot, stock, patched, manifest, fault):
    profile = identify_bootloader(boot, admitted=False)
    link = TimedLink(boot, stock, patched, fault)
    client = tool.Bootloader(link, profile, link.clock, link.sleep)
    try:
        if recovering:
            client.transfer_recovering(patched, stock, manifest)
        else:
            client.transfer(patched, manifest)
    except (TimeoutError, tool.RecoveryFailed):
        pass
    if link.state == "bootloader":
        link.advance(30)
    if link.state != "bricked":
        return link.state
    window = link.window
    if window and window[0] == "dead" and link.resets and window[2] >= link.resets[-1] + profile.startup_ticks / 1000:
        return "bricked-unavoidable"
    return "bricked-avoidable"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-image", required=True, type=Path)
    parser.add_argument("--patched-image", required=True, type=Path)
    parser.add_argument("--bootloader-backup", required=True, type=Path, help="captured image of a recoverable build")
    parser.add_argument("--quick", action="store_true", help="3 s and 12 s faults only")
    args = parser.parse_args()
    manifest = json.loads(tool.MANIFEST.read_text())
    stock, patched, boot = (path.read_bytes() for path in (args.stock_image, args.patched_image, args.bootloader_backup))
    assert tool.admitted_image(stock, manifest) == manifest["thr"]["stock_sha256"]
    assert tool.admitted_image(patched, manifest) == manifest["thr"]["patched_sha256"]
    assert identify_bootloader(boot, admitted=False).recoverable, "Bootloader has no validated recovery profile"
    durations = (3, 12) if args.quick else DURATIONS
    faults = [None] + [(mode, trigger, duration) for mode in ("dead", "lost-reply")
                       for trigger in TRIGGERS for duration in durations]
    outcomes = {"transfer": collections.Counter(), "transfer_recovering": collections.Counter()}
    avoidable = []
    for fault in faults:
        outcomes["transfer"][run(False, boot, stock, patched, manifest, fault)] += 1
        outcome = run(True, boot, stock, patched, manifest, fault)
        outcomes["transfer_recovering"][outcome] += 1
        if fault is None:
            assert outcome == "patched", "Uninterrupted recovering transfer did not install the patched image"
        if outcome == "bricked-avoidable":
            avoidable.append(fault)
    print(json.dumps({"bootloader_sha256": tool.digest(boot), "faults": len(faults),
                      "outcomes": {name: dict(counter) for name, counter in outcomes.items()}}, indent=2))
    assert not avoidable, f"Recovering transfer bricked a recoverable board: {avoidable}"


if __name__ == "__main__":
    main()
