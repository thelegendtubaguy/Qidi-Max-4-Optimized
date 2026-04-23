# Development

## Build, copy, and dry-run on a printer

Run the helper from the repo root:

```bash
scripts/build_copy_dry_run.sh --host 192.168.20.165
```

Default SSH user is `qidi`.

Use a different SSH user:

```bash
scripts/build_copy_dry_run.sh --host 192.168.20.165 --user other-user
```

Use a password instead of SSH keys:

```bash
scripts/build_copy_dry_run.sh --host 192.168.20.165 --password 'your-password'
```

Add installer debug output to the remote dry-run:

```bash
scripts/build_copy_dry_run.sh --host 192.168.20.165 --debug
```

Password-based runs require local `sshpass`.

## Testing

Run the focused installer core test suite:

```bash
python3 scripts/run_installer_core_tests.py
```

Validate that `installer/package.yaml` and `installer/supported_upgrade_sources.yaml` agree on supported installed-package versions:

```bash
python3 scripts/check_installer_known_versions.py
```

Validate that the OrcaSlicer and QIDI Studio machine G-code packs only reference known macros and allowed external commands:

```bash
python3 scripts/check_optimized_slicer_macros.py
```

Build the release-shaped installer bundle and smoke-test the extracted launchers against fixture runtime trees:

```bash
python3 scripts/build_installer_bundle.py --output-dir dist --channel release --smoke-test
```

Build the dev installer bundle and smoke-test the extracted launchers against fixture runtime trees:

```bash
python3 scripts/build_installer_bundle.py --output-dir dist --channel dev --build-id local --smoke-test
```

If you changed `installer/klipper/tltg-optimized-macros/`, run the formatter before finishing:

```bash
python3 scripts/format_klipper_configs.py
```

## Runtime override hooks

`installer/runtime/cli.py` accepts these environment overrides:

- `TLTG_OPTIMIZED_PRINTER_DATA_ROOT`
- `TLTG_OPTIMIZED_FIRMWARE_MANIFEST`
- `TLTG_OPTIMIZED_MOONRAKER_URL`

`installer/tests/helpers.py` and `scripts/smoke_test_installer_bundle.py` use those overrides to run against fixture runtime trees instead of a live printer.
