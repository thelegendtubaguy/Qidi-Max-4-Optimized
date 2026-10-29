## 1. Fork release

- [x] 1.1 Port the Max 4 Fluidd features to the fork and validate them against the test printer.
- [x] 1.2 Release workflow publishes `fluidd.zip` for `vX.Y.Z-tltg-<hash>` tags without Docker images.
- [x] 1.3 Tag `v1.37.7-tltg-d9ad446` and pin its URL and checksum in `installer/package.yaml`.

## 2. Implementation

- [x] 2.1 Manifest pin and bundle-builder download with checksum verification and cache.
- [x] 2.2 Package-owned build operation: verified extraction, staging, rename swap, marker, compensation, journal recovery, restoration.
- [x] 2.3 nginx site patch serves the build; nginx operation gated on a current build.
- [x] 2.4 Bundle and service-worker operations retire while the build is served.
- [x] 2.5 Uninstall restores nginx before removing the build.
- [x] 2.6 Lifecycle test covers fallback, switch with rollback, retirement, update with rollback, and uninstall.
- [x] 2.7 Update `README.md`, `CHANGELOG.md` under `26.10.29.1`, and the version.
- [x] 2.8 Uninstall always restores policy-independent host changes; the prompt covers only optional OS optimizations.
- [x] 2.9 Guarded Moonraker patch: 3MF prints started without a plate number use the sliced plate.
- [x] 2.10 Guarded allowed-services patch: Fluidd's service controls list `qidi-client`.
- [x] 2.11 Install and uninstall wait for Moonraker to report printer state before the pending Klipper restart.

## 3. Verification

- [x] 3.1 Installer core tests, OpenSpec validation, known-versions check, and the bundle smoke test pass.
- [x] 3.2 Install on the test printer: nginx serves the build, QIDI's bundle and service worker return to stock, and a tab that had QIDI's Fluidd open shows the build after one normal reload, over plain HTTP and with QIDI's service worker.
- [x] 3.3 Uninstall on the test printer, with the system-restoration prompt declined, serves QIDI's Fluidd again, removes the build, restores every policy-independent host change, keeps the optional OS optimizations, and an open tab of the build switches back by itself.
