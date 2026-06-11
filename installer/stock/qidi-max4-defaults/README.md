# QIDI Max 4 stock config snapshots

Source repository: https://github.com/thelegendtubaguy/Qidi-Max4-Defaults

Runtime restore path: `installer/runtime/legacy_manual_install.py`.

Bundled restore roots:

- `installer/stock/qidi-max4-defaults/firmwares/01.01.06.03/config/`
- `installer/stock/qidi-max4-defaults/firmwares/01.01.06.04/config/`

Legacy manual-install reset selects the restore root by detected firmware.

Excluded runtime files: `config/MCU_ID.cfg`, `config/box.cfg`, `config/fluidd.cfg`, and `config/saved_variables.cfg`.
