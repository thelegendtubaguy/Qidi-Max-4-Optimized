# Zram swap kernel modules

QIDI's Max 4 kernel can swap but ships without zram, so the installer's [zram swap](../docs/install.md#os-optimizations) brings its own modules: `lz4_compress`, `lz4_decompress`, `lz4`, `zsmalloc`, and `zram`. They are committed in [`installer/system/zram/`](../installer/system/zram/), and [`installer/package.yaml`](../installer/package.yaml) (`system_optimizations.zram_swap`) records their SHA-256 hashes, load order, and the one kernel build they load on:

```text
5.10.160 #4 SMP PREEMPT Wed Sep 3 15:21:57 CST 2025
```

Both the installer and the boot script compare `/proc/sys/kernel/osrelease` and `/proc/sys/kernel/version` with that build and load nothing on any other kernel.

## Rebuild and check

With Docker on a development computer, from the repository root:

```bash
python3 scripts/build_zram_modules.py --output-dir dist/zram-modules
```

The output directory must not exist. The script builds in an amd64 Debian container from pinned inputs:

- Kernel source: [armbian/linux-rockchip](https://github.com/armbian/linux-rockchip) commit `709c51c64e1652d4f8c87b1815db86f56d188268` (branch `rk-5.10-rkr6`, Linux 5.10.160).
- Toolchain: Arm GNU Toolchain 10.3-2021.07 `aarch64-none-linux-gnu`, the compiler `/proc/version` names on the printer, checked against its SHA-256.
- Configuration: [`qidi_max4_zram_defconfig`](qidi_max4_zram_defconfig).

It strips debug information, prints each module's hash, and exits non-zero when any differs from `installer/package.yaml`. Each module's build ID hashes its debug information, which records the build paths, so the script always builds under `/w`. After an intentional change, `--install` copies the new modules into `installer/system/zram/`; update the hashes in `installer/package.yaml` from its output.

## How the configuration matches QIDI's kernel

QIDI publishes neither its kernel source nor its configuration, and the printer has no `/proc/config.gz`. The configuration was rebuilt from the printer:

1. Start from Rockchip's `rk3308_linux_defconfig`, build built-in what it builds as modules, and add what the printer's `/proc/kallsyms` shows: swap, cgroups (`cpu`, `cpuacct`, `cpuset`, `devices`, `freezer`) with CFS bandwidth, CMA and `ZONE_DMA32`, CAN with `gs_usb`, SCSI and USB storage, the USB host controllers, USB serial (`ch341`), ACM, UVC, the DVB core, FUSE, autofs, the Goodix touchscreen, and dynamic debug. Tuners and DVB front ends are off.
2. Build `vmlinux` and compare its code symbols with `/proc/kallsyms`. With this configuration only three of about 37,000 differ, and the kernel image is within 66 bytes of the `Image` in the printer's boot partition (`/dev/block/by-name/boot`, an Android boot image holding an LZ4-compressed `Image`).
3. Turn on `BLK_DEV`, `ZSMALLOC`, `ZRAM`, `CRYPTO_LZ4`, and `CRYPTO_LZO` as modules. The kernel image stays byte-identical.

Modules depend on more than symbol names, so the build was checked against the code QIDI's kernel runs:

- The kernel has no `MODVERSIONS`; loading checks only the vermagic `5.10.160 SMP preempt mod_unload aarch64`, which matches.
- Every symbol the modules import is exported by QIDI's kernel, read from `__ksymtab_strings` in its `Image`.
- The block-layer, gendisk, bio, crypto, slab, page-allocator, and swap functions zram calls compile to the same instructions as in QIDI's `Image`, apart from relocated addresses, so the structure layouts they share agree.
- `struct module` has the same size and `init` and `exit` offsets as a module QIDI built for this kernel.
- This Android-derived tree counts `NR_ZSPAGES` whether or not zsmalloc is configured, and the printer's `/proc/vmstat` has `nr_zspages`, so zsmalloc's page accounting matches.

On the test printer, the loaded modules round-tripped 64 MB of real printer files through `/dev/zram0` byte for byte with both lz4 and lzo-rle.
