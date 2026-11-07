#!/usr/bin/env python3
"""Restricted Max 4 mainboard (USB) snapshots, transfers, and readback verification."""
from __future__ import annotations

import logging

if __package__:
    from .build_mcu_firmware import PATCH_MANIFEST
    from .flash_box_firmware import Board, main
else:
    from build_mcu_firmware import PATCH_MANIFEST
    from flash_box_firmware import Board, main

# The mainboard's DRIVER BOOT bootloader enumerates as 28e9:018a. With the first
# application page erased, as after any failed transfer, it stays waiting, also
# through a power cycle; turning the printer off and on also restarts this host.
MAINBOARD = Board("mainboard", "stm32f407xx", PATCH_MANIFEST, ("28e9", "018a"), 0x18000,
                  "if it does not appear, turn the printer off and on, then run rescue again")


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    raise SystemExit(main(board=MAINBOARD))
