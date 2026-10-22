"""Exact Max 4 THR build identities and their recovered transfer profiles."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class BootloaderProfile:
    sha256: str
    identity_reply: bytes
    start_reply: bytes
    end_reply: bytes
    final_padding: bytes
    erase_range: tuple[int, int, int]
    packet_zero_retry_safe: bool
    initialize: tuple[int, ...]
    controller_hooks: tuple[int, ...]
    erase_hook: int
    program_hook: int
    send_hook: int
    jump_hook: int
    dispatch: int
    receive_buffer: int
    receive_flags: tuple[int, ...]
    session_timer: int
    exit_timer: int
    reset_hook: int | None = None
    tick: int | None = None
    startup_ticks: int | None = None


FIRST = BootloaderProfile(
    sha256="46358f306156edbdee1822dcca17206f78241b01a7e96587215860c4b0d34fc6",
    identity_reply=bytes.fromhex("01020102"),
    start_reply=b"\x01\x01", end_reply=b"\x02\x01", final_padding=b"\xff",
    erase_range=(0x08008000, 0x08020000, 2048), packet_zero_retry_safe=False,
    initialize=(0x08000c10,),
    controller_hooks=(0x08000498, 0x08000508, 0x080004e0),
    erase_hook=0x080005c4, program_hook=0x08000690,
    send_hook=0x080016d4, jump_hook=0x08000b74,
    dispatch=0x080014d8, receive_buffer=0x20000458,
    receive_flags=(0x20000c62, 0x2000003d),
    session_timer=0x20000034, exit_timer=0x20000008,
)
SECOND = BootloaderProfile(
    sha256="31f8344db7b091df5429960bc9cd06065e2188c3b8092e43fb65eb3f2833723c",
    identity_reply=bytes.fromhex("0102"),
    start_reply=b"\x01\x01", end_reply=b"\x02\x01", final_padding=b"\x00",
    erase_range=(0x08008000, 0x08020000, 2048), packet_zero_retry_safe=False,
    initialize=(0x08001d04, 0x08001cdc),
    controller_hooks=(0x08000fbc, 0x08000ff4, 0x08001162),
    erase_hook=0x08001018, program_hook=0x080010cc,
    send_hook=0x08000c74, jump_hook=0x08000aac,
    dispatch=0x0800014e, receive_buffer=0x20000084,
    receive_flags=(0x2000088e, 0x2000000b),
    session_timer=0x20000014, exit_timer=0x20000018,
    reset_hook=0x08000130, tick=0x08001bfc, startup_ticks=4000,
)
PROFILES = {profile.sha256: profile for profile in (FIRST, SECOND)}
# Admission requires matching offline checks and live non-erasing evidence.
ADMITTED_BOOTLOADERS = frozenset((FIRST.sha256, SECOND.sha256))


def identify_bootloader(data: bytes, *, admitted: bool = True) -> BootloaderProfile:
    identity = hashlib.sha256(data).hexdigest()
    if len(data) != 0x8000 or identity not in PROFILES or (admitted and identity not in ADMITTED_BOOTLOADERS):
        raise ValueError("Unrecognized bootloader")
    return PROFILES[identity]
