# QIDI Plus 5 stock config snapshots

Source repository: https://github.com/thelegendtubaguy/Qidi-Plus5-Defaults

Runtime restore path: `installer/runtime/legacy_manual_install.py`.

Bundled restore roots:

- `installer/stock/qidi-plus5-defaults/firmwares/01.01.02.01/config/`

Firmware `01.01.02.01` uses defaults commit `25001402d9025dc9f494e51f2cba907f8e1b45d6`, release archive `QD_PLUS5_01.01.02.01_20261016_Release.zip` with SHA-256 `534e5ce959b1e387fc6355f8d78736ddb94432eb9c569ff2a135e103dfeb0871`, firmware-manifest SHA-256 `085259c173e9bf13978552f79b3f37db6a5f470f12dd6a2c248f284754efddd6`, and SOC payload SHA-256 `43ea5068c624e2fc0ab41e94c75c6f4a05e0dd0480654f8b52dc8bbabde4cae6`. QIDI ships these files with CRLF line endings, and the snapshot keeps them; only copyright e-mail addresses are redacted.

Legacy manual-install reset selects the restore root by detected firmware.

Excluded runtime files: `config/MCU_ID.cfg`, `config/box.cfg`, `config/fluidd.cfg`, and `config/saved_variables.cfg`.
