## ADDED Requirements

### Requirement: Package-owned Klipper extra modules
Install and update SHALL place each bundled package-owned Klipper extra module, together with the optimized configuration section that loads it, and uninstall SHALL remove the module only when it still matches the bundled payload.

#### Scenario: Install places and verifies the module
- **WHEN** install or update runs
- **THEN** each bundled extra module is written atomically to its `klippy/extras/tltg_*.py` destination and verified against the bundled payload
- **AND** an identical installed module is left unchanged

#### Scenario: Uninstall respects modified modules
- **WHEN** uninstall runs
- **THEN** an installed extra module that matches the bundled payload is removed along with the optimized configuration that loads it
- **AND** a modified module is left in place

### Requirement: QIDI Box motion settings in Fluidd
Normal install and update SHALL extend the recognized QIDI Fluidd bundle's Box Config view with a load and unload motion section that shows the feed-motion status and edits settings only through `TLTG_BOX_MOTION`, with the same recognition, preservation, service-worker revision, and restoration as the other Fluidd Box patches.

#### Scenario: Motion settings are shown per slot
- **WHEN** the feed-motion printer object is active
- **THEN** the Box Config view shows the global settings with vendor values for unset fields, and each slot's effective load and unload profile, its overrides, and the reason when a profile falls back to vendor motion

#### Scenario: Motion settings are edited through the command
- **WHEN** an operator applies global or slot settings, or resets them from the section
- **THEN** Fluidd sends the matching `TLTG_BOX_MOTION` command
- **AND** a refused command's reason is shown in the section

#### Scenario: Editing is unavailable while busy or inactive
- **WHEN** a print is running or paused, or the feed-motion object is absent or inactive
- **THEN** the section offers no editing controls, and an absent or inactive object shows its status instead of a profile

### Requirement: QIDI Box motion release defaults
The installer SHALL save the release Box motion profile only when no Box motion setting exists in Klipper saved variables.

#### Scenario: Printers without motion settings receive the release profile
- **WHEN** install, update, or idle automatic-update repair finds none of the Box motion settings
- **THEN** it saves the release profile through Moonraker after Klipper is ready and verifies the live values

#### Scenario: Operator motion settings are preserved
- **WHEN** any Box motion setting exists, including one saved as `None` to use the vendor value
- **THEN** no motion setting is written
- **AND** uninstall does not remove or reset the settings
