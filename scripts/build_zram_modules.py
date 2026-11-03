#!/usr/bin/env python3
"""Rebuild the zram swap kernel modules for QIDI's Max 4 kernel and check them against the package manifest.

The modules are built in Docker from a pinned Rockchip 5.10.160 tree with the exact Arm toolchain QIDI's kernel was
built with, using kernel/qidi_max4_zram_defconfig. See kernel/README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from installer.runtime.manifest import load_manifest

KERNEL_REPOSITORY = "https://github.com/armbian/linux-rockchip"
# Branch rk-5.10-rkr6, Linux 5.10.160.
KERNEL_COMMIT = "709c51c64e1652d4f8c87b1815db86f56d188268"
# /proc/version on the printer names this toolchain. Arm now hosts only its x86_64 build, so Docker runs amd64.
TOOLCHAIN_URL = (
    "https://armkeil.blob.core.windows.net/developer/Files/downloads/gnu-a/10.3-2021.07/binrel/"
    "gcc-arm-10.3-2021.07-x86_64-aarch64-none-linux-gnu.tar.xz"
)
TOOLCHAIN_SHA256 = "1e33d53dea59c8de823bbdfe0798280bdcd138636c7060da9d77a97ded095a84"
BUILD_IMAGE = "debian:bookworm@sha256:d74df7598108a173a621eda4d58a2adbf850b2d9a9d81bc2cca1a6c21174a880"
DEFCONFIG = REPO_ROOT / "kernel/qidi_max4_zram_defconfig"
# Where each module is built in the kernel tree.
TREE_PATHS = {
    "lz4_compress": "lib/lz4/lz4_compress.ko",
    "lz4_decompress": "lib/lz4/lz4_decompress.ko",
    "lz4": "crypto/lz4.ko",
    "zsmalloc": "mm/zsmalloc.ko",
    "zram": "drivers/block/zram/zram.ko",
}

BUILD_SCRIPT = r"""
set -eu
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    make bc flex bison libssl-dev libelf-dev python3 git xz-utils curl ca-certificates kmod cpio gcc libc6-dev >/dev/null
# The build ID in each module hashes its debug info, which records these paths, so they are part of the build.
mkdir /w
cd /w
curl -fsSL -o toolchain.tar.xz "$TOOLCHAIN_URL"
echo "$TOOLCHAIN_SHA256  toolchain.tar.xz" | sha256sum -c - >/dev/null
tar xf toolchain.tar.xz
git init -q linux
cd linux
git fetch -q --depth 1 "$KERNEL_REPOSITORY" "$KERNEL_COMMIT"
git checkout -q FETCH_HEAD
# Armbian adds this vendor Ethernet driver unconditionally and it fails to build with this toolchain. QIDI's kernel
# doesn't have it, and nothing else in the build depends on it.
sed -i 's/^obj-m += yt6801.o/#&/' drivers/net/ethernet/motorcomm/Makefile
cp /input/qidi_max4_zram_defconfig arch/arm64/configs/
export ARCH=arm64 CROSS_COMPILE=/w/gcc-arm-10.3-2021.07-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-
make -s qidi_max4_zram_defconfig
# vmlinux first, so modpost checks the modules' symbols against it.
make -s -j"$(nproc)" vmlinux
make -s -j"$(nproc)" modules
for entry in $MODULES; do
    "${CROSS_COMPILE}strip" --strip-debug -o "/out/${entry%%=*}.ko" "${entry#*=}"
done
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output_dir: Path) -> None:
    output_dir.mkdir(parents=True)
    modules = " ".join(f"{name}={path}" for name, path in TREE_PATHS.items())
    subprocess.run(
        [
            "docker", "run", "--rm", "--platform", "linux/amd64",
            "-v", f"{DEFCONFIG.parent}:/input:ro",
            "-v", f"{output_dir.resolve()}:/out",
            "-e", f"KERNEL_REPOSITORY={KERNEL_REPOSITORY}",
            "-e", f"KERNEL_COMMIT={KERNEL_COMMIT}",
            "-e", f"TOOLCHAIN_URL={TOOLCHAIN_URL}",
            "-e", f"TOOLCHAIN_SHA256={TOOLCHAIN_SHA256}",
            "-e", f"MODULES={modules}",
            BUILD_IMAGE, "bash", "-c", BUILD_SCRIPT,
        ],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory for the built modules.")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Copy the built modules into installer/system/zram after printing their hashes.",
    )
    args = parser.parse_args(argv)
    if args.output_dir.exists() or args.output_dir.is_symlink():
        parser.error(f"{args.output_dir} already exists")
    if shutil.which("docker") is None:
        parser.error("docker is required")

    spec = load_manifest(REPO_ROOT / "installer/package.yaml").system_optimizations.zram_swap
    if [module.name for module in spec.modules] != list(TREE_PATHS):
        parser.error("installer/package.yaml zram_swap.modules doesn't match the modules this script builds")
    build(args.output_dir)

    mismatched = []
    for module in spec.modules:
        built = args.output_dir / f"{module.name}.ko"
        actual = sha256(built)
        print(f"{module.name}.ko {actual}")
        if actual != module.sha256:
            mismatched.append(module.name)
        if args.install:
            shutil.copy2(built, REPO_ROOT / "installer" / module.archive)
    if mismatched and not args.install:
        print(f"Built modules differ from installer/package.yaml: {', '.join(mismatched)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
