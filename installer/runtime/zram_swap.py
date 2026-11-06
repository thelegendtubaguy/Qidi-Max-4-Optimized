from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import InstallerError
from .models import SystemZramSwapSpec


# QIDI's kernel can swap but ships no zram, and its RAM is small enough that a long print with AI detection running can
# exhaust it. Without swap the kernel can only drop program code, which Klipper then re-reads from eMMC, stalling it
# until the MCU shuts down. Compressed swap in RAM lets the kernel move idle memory aside instead. The package builds
# zram and its compressor for QIDI's exact kernel build; the boot script refuses to load them on any other kernel.
OPERATION = "zram_swap"
UNIT_OPERATION = "zram_swap_unit"
DESTINATION = "/usr/local/lib/tltg-zram-swap"
STAGING = f"{DESTINATION}.tltg-staging"
PREVIOUS = f"{DESTINATION}.tltg-previous"
REMOVING = f"{DESTINATION}.tltg-removing"
# Marks the directory as package-owned and records the files it was installed with.
MARKER = ".tltg-zram-swap"
SCRIPT = "tltg-zram-swap.sh"
UNIT = "tltg-zram-swap.service"
UNIT_FILE = f"/etc/systemd/system/{UNIT}"
OSRELEASE = "/proc/sys/kernel/osrelease"
VERSION = "/proc/sys/kernel/version"
DEVICE = "/dev/zram0"
# Kernel defaults, restored when zram swap stops.
DEFAULT_SWAPPINESS = 60
DEFAULT_PAGE_CLUSTER = 3
SWAP_PRIORITY = 100

ABSENT = "absent"
CURRENT = "current"
OUTDATED = "outdated"
FOREIGN = "foreign"

# Package-created units start with a marker line so later package versions replace earlier ones.
UNIT_MARKER = "# tltg-optimized:zram-swap\n"
UNIT_CONTENT = UNIT_MARKER + f"""\
# Compressed swap in RAM (zram). Installed by Valve Oil.
[Unit]
Description=Compressed swap in RAM (zram)
Before=klipper.service moonraker.service qidi-client.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={DESTINATION}/{SCRIPT} start
ExecStop={DESTINATION}/{SCRIPT} stop

[Install]
WantedBy=multi-user.target
"""


class ZramSwapError(InstallerError):
    pass


def patch_unit(current: str) -> str:
    if current == "" or current.startswith(UNIT_MARKER):
        return UNIT_CONTENT
    raise InstallerError(f"Existing {UNIT_FILE} is unrecognized and was preserved.")


def kernel_supported(spec: SystemZramSwapSpec, *, osrelease: Path, version: Path) -> bool:
    """Whether the running kernel is the exact build the modules were made for."""
    try:
        return (
            osrelease.read_text(encoding="utf-8").strip() == spec.kernel_release
            and version.read_text(encoding="utf-8").strip() == spec.kernel_version
        )
    except OSError:
        return False


def render_script(spec: SystemZramSwapSpec) -> str:
    names = [module.name for module in spec.modules]
    return f"""#!/bin/sh
# Compressed swap in RAM (zram). Installed by Valve Oil.
set -u
DIR={DESTINATION}
RELEASE='{spec.kernel_release}'
VERSION='{spec.kernel_version}'
ZRAM=/sys/block/zram0

loaded() {{
    grep -q "^$1 " /proc/modules
}}

start() {{
    # The modules match one kernel build. Any other kernel, such as one from a QIDI update, runs without swap.
    if [ "$(cat {OSRELEASE})" != "$RELEASE" ] || [ "$(cat {VERSION})" != "$VERSION" ]; then
        echo "Kernel $(cat {OSRELEASE}) $(cat {VERSION}) is not the build these modules are for; zram swap stays off."
        return 0
    fi
    for module in {" ".join(names)}; do
        loaded "$module" || insmod "$DIR/$module.ko" || return 1
    done
    if ! grep -q '^{DEVICE} ' /proc/swaps; then
        [ "$(cat $ZRAM/disksize)" = 0 ] || echo 1 > $ZRAM/reset || return 1
        echo {spec.algorithm} > $ZRAM/comp_algorithm || return 1
        echo {spec.size_mb}M > $ZRAM/disksize || return 1
        tries=0
        while [ ! -b {DEVICE} ] && [ $tries -lt 50 ]; do
            sleep 0.1
            tries=$((tries + 1))
        done
        mkswap {DEVICE} > /dev/null || return 1
        swapon -p {SWAP_PRIORITY} {DEVICE} || return 1
    fi
    echo {spec.swappiness} > /proc/sys/vm/swappiness
    echo {spec.page_cluster} > /proc/sys/vm/page-cluster
}}

stop() {{
    echo {DEFAULT_SWAPPINESS} > /proc/sys/vm/swappiness
    echo {DEFAULT_PAGE_CLUSTER} > /proc/sys/vm/page-cluster
    if grep -q '^{DEVICE} ' /proc/swaps; then
        swapoff {DEVICE} || return 1
    fi
    for module in {" ".join(reversed(names))}; do
        ! loaded "$module" || rmmod "$module" || return 1
    done
}}

case "${{1:-}}" in
    start) start ;;
    stop) stop ;;
    *) echo "usage: $0 start|stop" >&2; exit 2 ;;
esac
"""


def files(spec: SystemZramSwapSpec, installer_root: Path) -> dict[str, bytes]:
    """Return the verified directory contents keyed by file name."""
    contents: dict[str, bytes] = {SCRIPT: render_script(spec).encode("utf-8")}
    for module in spec.modules:
        try:
            data = (installer_root / module.archive).read_bytes()
        except OSError as exc:
            raise ZramSwapError(f"Kernel module {module.name} is missing from the package.") from exc
        if hashlib.sha256(data).hexdigest() != module.sha256:
            raise ZramSwapError(f"Kernel module {module.name} checksum does not match the package manifest.")
        contents[f"{module.name}.ko"] = data
    return contents


def bundled(spec: SystemZramSwapSpec, installer_root: Path) -> bool:
    return all((installer_root / module.archive).is_file() for module in spec.modules)


def digest(contents: dict[str, bytes]) -> str:
    return hashlib.sha256(
        "\n".join(f"{name} {hashlib.sha256(data).hexdigest()}" for name, data in sorted(contents.items())).encode("ascii")
    ).hexdigest()


def installed_digest(destination: Path) -> str | None:
    """Return the digest recorded in a package-owned directory, or None when it is not one."""
    marker = destination / MARKER
    if destination.is_symlink() or not destination.is_dir() or marker.is_symlink() or not marker.is_file():
        return None
    return marker.read_text(encoding="utf-8").strip()


def state(destination: Path, contents: dict[str, bytes]) -> str:
    if not destination.exists() and not destination.is_symlink():
        return ABSENT
    installed = installed_digest(destination)
    if installed is None:
        return FOREIGN
    if installed != digest(contents):
        return OUTDATED
    for name, data in contents.items():
        target = destination / name
        if target.is_symlink() or not target.is_file() or target.read_bytes() != data:
            return OUTDATED
    return CURRENT


def write_tree(contents: dict[str, bytes], target: Path) -> None:
    """Write the directory contents into a new directory, writing the marker last."""
    target.mkdir(mode=0o755)
    target.chmod(0o755)
    for name, data in contents.items():
        path = target / name
        path.write_bytes(data)
        path.chmod(0o755 if name == SCRIPT else 0o644)
    marker = target / MARKER
    marker.write_text(f"{digest(contents)}\n", encoding="utf-8")
    marker.chmod(0o644)
