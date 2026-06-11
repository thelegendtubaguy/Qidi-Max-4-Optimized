## ADDED Requirements

### Requirement: Supported firmware baselines
The installer SHALL support QIDI Max 4 firmware `01.01.06.03` and `01.01.06.04` as separate stock baselines.

#### Scenario: Firmware 01.01.06.03 is accepted
- **WHEN** the detected firmware version is `01.01.06.03`
- **THEN** installer firmware validation passes
- **AND** guarded patch variants for `01.01.06.03` are selected

#### Scenario: Firmware 01.01.06.04 is accepted
- **WHEN** the detected firmware version is `01.01.06.04`
- **THEN** installer firmware validation passes
- **AND** guarded patch variants for `01.01.06.04` are selected

#### Scenario: Unsupported firmware is rejected
- **WHEN** the detected firmware version is not listed in `installer/package.yaml firmware.supported`
- **THEN** installation stops before reading `config/tltg_optimized_state.yaml`, creating a backup, or writing under `config/`

### Requirement: Firmware-specific patch variants
Every guarded patch target in `installer/package.yaml` SHALL define at least one supported firmware variant and SHALL be active only for firmware versions listed by its variants.

#### Scenario: Manifest covers applicable firmware versions
- **WHEN** manifest validation reads `installer/package.yaml`
- **THEN** every `patches.set_options[]` target defines at least one variant using a supported firmware version
- **AND** every `patches.delete_sections[]` target defines at least one variant using a supported firmware version
- **AND** no patch target defines more than one variant for the same firmware

#### Scenario: Firmware 01.01.06.03 keeps pre-01.01.06.04 expectations
- **WHEN** installation runs on firmware `01.01.06.03`
- **THEN** expected values for QIDI stock fields changed by `01.01.06.04` match the `01.01.06.03` baseline
- **AND** `.04`-only closed-loop `trigger_*` patch targets are not active for `.03` preflight success

#### Scenario: Firmware 01.01.06.04 uses 01.01.06.04 expectations
- **WHEN** installation runs on firmware `01.01.06.04`
- **THEN** expected values for QIDI stock fields changed by `01.01.06.04` match the `01.01.06.04` baseline
- **AND** X/Y closed-loop stock expectations include `query_cycle:10`, `trigger_current:400`, `trigger_time:2`, and `trigger_speed:50`

### Requirement: Firmware-specific legacy stock restore
Legacy manual-install reset SHALL restore a stock config snapshot matching the detected firmware baseline.

#### Scenario: Legacy reset on firmware 01.01.06.03
- **WHEN** legacy manual-install markers are detected and the detected firmware is `01.01.06.03`
- **THEN** the reset restores the `01.01.06.03` stock snapshot
- **AND** firmware-specific files from the `01.01.06.04` stock snapshot are not written

#### Scenario: Legacy reset on firmware 01.01.06.04
- **WHEN** legacy manual-install markers are detected and the detected firmware is `01.01.06.04`
- **THEN** the reset restores the `01.01.06.04` stock snapshot
- **AND** firmware-specific files from the `01.01.06.03` stock snapshot are not written

#### Scenario: Stock snapshot missing for accepted firmware
- **WHEN** legacy manual-install reset is accepted for a supported firmware
- **AND** the firmware-matched stock snapshot is missing or invalid
- **THEN** the installer fails before stock files are overwritten

### Requirement: QIDI 01.01.06.04 stock deltas
The `01.01.06.04` stock baseline SHALL represent QIDI's shipped config changes from `Qidi-Max4-Defaults` commit `5da5767379ac22fc4fbe1606ec7093ce056229ae`.

#### Scenario: Closed-loop stock values match 01.01.06.04
- **WHEN** the `01.01.06.04` stock baseline is inspected
- **THEN** `[closed_loop x]` and `[closed_loop y]` contain `query_cycle:10`
- **AND** each section contains `trigger_current:400`, `trigger_time:2`, and `trigger_speed:50`

#### Scenario: Idle pause temperature target matches 01.01.06.04
- **WHEN** the `01.01.06.04` stock baseline is inspected
- **THEN** `_km_idle_timeout` saves `saved_extruder_temp` on `RESUME_PRINT`

#### Scenario: Chamber protection threshold matches 01.01.06.04
- **WHEN** the `01.01.06.04` stock baseline is inspected
- **THEN** `Chamber_Thermal_Protection_Sensor max_temp` is `170`

#### Scenario: Official PA-CF rename matches 01.01.06.04
- **WHEN** the `01.01.06.04` official filament list is inspected
- **THEN** `[fila25] filament` is `PA6-CF`
- **AND** `[fila25] type` is `PA6-CF`

### Requirement: Optimized error cancel cleanup ordering
`OPTIMIZED_CANCEL_PRINT_ON_ERROR` SHALL call `_KM_CANCEL_PRINT_BASE` after heater shutdown, fan shutdown, pause-state restore, `G31`, and `CLEAR_PAUSE` while preserving its no-park and no-toolhead-move cancel behavior.

#### Scenario: Virtual SD error cancel finalizes after cleanup
- **WHEN** `OPTIMIZED_CANCEL_PRINT_ON_ERROR` is executed
- **THEN** heaters and fans are shut down before `_KM_CANCEL_PRINT_BASE`
- **AND** pause-state restore, `G31`, and `CLEAR_PAUSE` are executed before `_KM_CANCEL_PRINT_BASE`
- **AND** no park or wipe motion is added to the optimized error cancel path

### Requirement: Documentation for firmware baseline behavior
Installer documentation SHALL describe firmware-specific support, stock snapshot selection, guarded patch coverage, and validation commands.

#### Scenario: Runtime contract documents firmware-specific behavior
- **WHEN** `docs/installer_runtime_contract.md` is inspected after implementation
- **THEN** it describes support for `01.01.06.03` and `01.01.06.04`
- **AND** it describes how legacy manual-install reset selects the stock snapshot for the detected firmware

#### Scenario: Validation commands are documented or run
- **WHEN** the change is completed
- **THEN** `python3 scripts/check_installer_known_versions.py` has been run
- **AND** installer runtime tests covering firmware-specific behavior have been run or the remaining validation gap is documented
