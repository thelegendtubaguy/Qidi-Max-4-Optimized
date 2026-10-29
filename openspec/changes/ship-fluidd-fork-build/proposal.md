## Why

QIDI no longer maintains the Fluidd it bundles with the Max 4 (v1.30.5, source unpublished), so every Fluidd fix and feature this project ships is a guarded patch of QIDI's minified bundle. Upstream Fluidd has moved on to v1.37.x and remains compatible with QIDI's Moonraker. The project now maintains a fork of upstream Fluidd with the Max 4 features (`thelegendtubaguy/fluidd`, branch `qidi`), and needs the installer to deliver it.

## What Changes

- The installer bundle carries a pinned release build of the fork, downloaded and checksum-verified by the bundle builder.
- Install and update extract the build into a package-owned directory beside QIDI's bundle and switch Fluidd's nginx site to serve it, in the same guarded nginx change that adds the printer-screen route, independently of optional OS optimization policy. QIDI's bundled Fluidd stays on disk as the rollback.
- While nginx serves the build, QIDI's bundle is no longer patched: unchanged files patched by earlier package versions are restored and their ownership released.
- When the build cannot be served (no build in the package, an unrecognized nginx site, or an unowned directory in the way), QIDI's Fluidd stays in use with the existing bundle patches.
- Uninstall restoration points nginx back at QIDI's bundle and then removes the build.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `installer-lifecycle`: serves the package-built Fluidd and scopes the Fluidd bundle patches to when QIDI's bundle is served.

## Impact

- New `installer/runtime/fluidd_build.py`; `installer/runtime/remote_screen.py` (nginx root), `installer/runtime/system_optimizations.py` (operation, ordering, retirement, restoration), manifest model and parser.
- `installer/package.yaml` pins the build; `scripts/build_installer_bundle.py` downloads it into the bundle, which grows by about 4.4 MB.
- Installer lifecycle tests; `README.md`; `CHANGELOG.md` under `26.10.28.3`.
- No Klipper config, macro, or slicer changes. QIDI's bundled Fluidd files are not modified.
