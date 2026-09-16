# optimized-printer-behavior Specification

## Purpose

Optimized printer behavior shortens print transitions while preserving QIDI motion safety, slicer compatibility, hardware monitoring, and vendor-owned QIDI Box behavior.

## Requirements

### Requirement: Guarded motion and calibration optimization
Optimized configuration SHALL reduce homing, probing, mesh, and filament-transition overhead only where the selected firmware baseline, valid installer state, or explicit saved-mesh preference proves the change safe.

#### Scenario: Recognized state receives optimized behavior
- **WHEN** supported stock or proven prior-managed motion and timing inputs are installed
- **THEN** guarded values and firmware-scoped payloads from `installer/package.yaml` are applied
- **AND** unrecognized live values are preserved as user-modified
- **AND** production payloads remain syntax-valid and exclude diagnostic-only commands

#### Scenario: Closed-loop homing safety remains intact
- **WHEN** X or Y homes
- **THEN** QIDI controller ordering, two-strike validation, retry/error handling, synchronization behavior for the selected firmware, and final backoff remain active
- **AND** reduced waits and speeds do not add firmware behavior absent from that baseline

#### Scenario: Homing and print preparation avoid redundant motion
- **WHEN** full, per-axis, or lazy homing and print preparation run
- **THEN** normal homing performs the requested axes, lazy homing skips requested axes already known, and Z homes required unknown X/Y first
- **AND** temporary motion settings are restored
- **AND** Z tilt and the selected fresh adaptive or named saved-mesh preparation run without redundant homing or stale active mesh state

#### Scenario: Runtime Z offset survives preparation
- **WHEN** start G-code captures the saved runtime Z offset
- **THEN** the offset is cleared before homing, tilt, and mesh preparation
- **AND** the captured value is reapplied after mesh preparation
- **AND** saved fallback is used only when the session has no capture

### Requirement: Controlled slicer start paths
OrcaSlicer and QIDI Studio packs SHALL implement the same functional print-start branches while printer-side Klipper state selects mesh preparation and parser-specific syntax and ordered invariants remain controlled by `openspec/contracts/gcode-paths/start-print.path.json`.

#### Scenario: Slicer entrypoints satisfy the path contract
- **WHEN** either slicer pack is validated
- **THEN** its required and forbidden commands, ordering, temperature inputs, selected tool, and parser-specific placeholders satisfy the controlled path contract
- **AND** no slicer start call supplies or configures a bed-mesh profile preference
- **AND** first-layer temperature and the selected tool are established before front-bed priming

#### Scenario: Existing printer state retains adaptive meshing
- **WHEN** `tltg_start_bed_mesh_profile` is absent from Klipper saved variables or contains an empty string
- **THEN** optimized print start reports fresh adaptive `kamp` calibration to the Klipper console
- **AND** it performs fresh adaptive `kamp` calibration
- **AND** the behavior applies to existing sliced files and both repository slicer packs
- **AND** the behavior applies to retained Box filament, fresh Box filament, and external-spool starts

#### Scenario: Named saved profile is selected persistently
- **WHEN** `tltg_start_bed_mesh_profile` contains a non-empty profile name
- **AND** the named saved profile exists
- **THEN** optimized print start reports the named saved profile to the Klipper console
- **AND** it clears stale active mesh state and asks Klipper to load that exact profile name
- **AND** it skips print-start bed-mesh calibration
- **AND** the behavior applies to existing sliced files and both repository slicer packs
- **AND** the behavior applies to retained Box filament, fresh Box filament, and external-spool starts

#### Scenario: Named profile is unavailable
- **WHEN** `tltg_start_bed_mesh_profile` contains a non-empty profile name
- **AND** Klipper cannot load that saved profile name
- **THEN** print preparation stops with Klipper's profile-load error
- **AND** it does not silently continue without mesh compensation or create a new mesh

#### Scenario: Saved-profile preference is operator-controlled
- **WHEN** the operator saves a non-empty string to `tltg_start_bed_mesh_profile`
- **THEN** subsequent optimized starts use that named profile until the saved value changes
- **AND** saving an empty string restores fresh adaptive calibration
- **AND** installation does not create or overwrite the optional preference

#### Scenario: Proven retained Box filament avoids reload
- **WHEN** Box availability, filament detection, logical mapping, synchronized physical slot, material, and vendor identity all prove retained-filament reuse
- **THEN** vendor loading and rear purge/cleanup actions are skipped
- **AND** common temperature waits, tilt, selected mesh preparation, offset, and sensor preparation still run

#### Scenario: Fresh Box filament retains vendor ownership
- **WHEN** the Box is enabled and retained reuse is not proven
- **THEN** start delegates feeder, cutter, retry, runout, RFID, and vendor cleaning ownership to the Box stack
- **AND** optimized purge cleanup runs before a full-width cable-chain orientation traverse and rear scraping across the stock Y395–Y397 footprint

#### Scenario: External spool avoids Box-only actions
- **WHEN** the Box is unavailable or disabled
- **THEN** retained Box state is invalidated and Box load or purge actions are not called
- **AND** non-extruding rear cleaning uses the same cable-chain orientation and stock Y395–Y397 scrape footprint before common print preparation

#### Scenario: Prime line remains first-layer aware
- **WHEN** common preparation completes
- **THEN** the prime line uses available room ahead of first-layer bounds or a fixed safe fallback
- **AND** nozzle-temperature Z compensation is applied from a known absolute reference after mesh and offset application

### Requirement: Optional minimum chamber startup temperature
Optimized print start SHALL accept a chamber startup minimum independently of the chamber heating target, with compatible slicer G-code for OrcaSlicer 2.4.2 and later.

#### Scenario: Positive minimum releases startup while heating continues
- **WHEN** OrcaSlicer start G-code supplies a positive minimum from the initial tool's filament profile
- **THEN** retained Box filament, fresh Box filament, and external-spool starts wait for that exact minimum before leveling
- **AND** the minimum is capped at the requested chamber target
- **AND** chamber heating retains the requested target throughout subsequent leveling and printing without another full-target wait
- **AND** a zero chamber target or unavailable chamber heater causes no chamber wait

#### Scenario: Independent slicer and macro updates preserve startup
- **WHEN** the minimum is omitted or zero
- **THEN** updated macros preserve the existing chamber startup wait threshold of target minus 3 degrees, bounded at zero
- **AND** existing sliced files and QIDI Studio starts retain their established behavior

#### Scenario: Updated slicer G-code remains usable with older macros
- **WHEN** updated OrcaSlicer start G-code runs against older optimized macros
- **THEN** the optional minimum parameter is ignored and the established chamber wait remains active

#### Scenario: Minimum applies to staggered heating
- **WHEN** staggered heating is enabled and target-bearing start G-code supplies a positive chamber minimum
- **THEN** the chamber stage waits for the minimum before its configured dwell and nozzle activation
- **AND** subsequent filament preparation uses the same minimum rather than waiting for the full target
- **AND** prior no-argument starts preserve their active-target heating behavior

### Requirement: Filament and QIDI Box state lifecycle
Optimized macros SHALL keep external-spool runout policy independent from vendor Box recovery, retain filament only when the saved preference equals `1` and physical Box state is provable, and normalize tool mappings only at safe lifecycle boundaries.

#### Scenario: External runout pause is independently switchable
- **WHEN** automatic external-spool pause is disabled
- **THEN** sensor events and exhausted status remain visible while automatic external pause is suppressed
- **AND** QIDI Box runout, reload, status, and resume remain vendor-controlled
- **AND** the setting returns enabled after Klipper restart

#### Scenario: Absent runtime preference disables retention
- **WHEN** `tltg_keep_loaded_between_prints` is absent from Klipper saved variables or does not equal `1`
- **THEN** normal optimized print completion clears retained-filament state and delegates cutting and unloading to the existing QIDI Box sequence
- **AND** runout sensors are disabled before the intentional end-of-print unload so it cannot pause the remaining shutdown routine
- **AND** optimized print start does not reuse retained filament

#### Scenario: Retention follows the synchronized physical slot
- **WHEN** `tltg_keep_loaded_between_prints` equals `1`
- **AND** normal end-print retention runs with Box filament loaded
- **THEN** retained tool, slot, material, and vendor identity derive from the synchronized physical slot and current mapping
- **AND** unload clears retained state before vendor unload while preserving caller motion and extrusion modes

#### Scenario: Retention preference is operator-controlled
- **WHEN** the operator saves `1` or `0` to `tltg_keep_loaded_between_prints`
- **THEN** subsequent optimized starts and normal completions respectively enable or disable retention until the saved value changes
- **AND** installation initializes an absent preference to `1` and does not overwrite an existing value

#### Scenario: Start repairs only missing active mappings
- **WHEN** print start requires active Box mappings
- **THEN** missing or empty active mappings become identity mappings before filament preparation
- **AND** every existing non-empty mapping is preserved
- **AND** non-Box start remains available

#### Scenario: Normal completion restores predictable mappings
- **WHEN** slicer end G-code completes retention or unloading
- **THEN** cooldown begins before existing mappings are normalized to identity
- **AND** missing mappings are created only for active Box slots
- **AND** normalization completes before print-end cleanup

#### Scenario: Interrupted prints preserve operator recovery state
- **WHEN** cancellation, error, power loss, or another interruption bypasses normal slicer end G-code
- **THEN** current tool mappings are not normalized
- **AND** manual mapping reset is permitted only while the printer is idle

### Requirement: Safe print transitions and helpers
Optimized cut, purge, cooldown, cleaning, calibration, and cancellation helpers SHALL preserve caller state, guard optional hardware, and avoid delayed or error-path actions that can affect a subsequent print. Print-start cleaning SHALL preserve staged cooldown wiping with mixed-speed pre-scrape motion and use fast finishing after the cooled rear-bed scrape, with detailed motion and branch ordering controlled by `openspec/contracts/gcode-paths/start-print.path.json`.

#### Scenario: Cut and cleanup preserve caller state
- **WHEN** optimized cut, purge, chute, chamber, or Box-heater helpers run
- **THEN** motion modes, extrusion modes, and temporary acceleration are restored
- **AND** optional Box objects are called only when available and valid
- **AND** fixed waits are reduced without replacing required motion completion waits

#### Scenario: Pre-scrape wiping retains the cooldown stages
- **WHEN** a fresh Box or external-spool start reaches an existing guarded pre-scrape chute wipe
- **THEN** each wipe uses two broad alternating-speed cycles followed by three finishing cycles at commanded 100 mm/s
- **AND** existing repeated cooldown wipe stages, temperature thresholds, conditional execution, purge quantities, and waste-release positioning are preserved rather than collapsed into one wipe
- **AND** the existing cooled rectangular rear-bed scrape is followed by three small circles with its cable-chain orientation and temperature safety gate intact

#### Scenario: Cooled scraping finishes with fast chute wiping
- **WHEN** a fresh Box or external-spool start completes its rear-bed scrape and guarded chute cleanup is available
- **THEN** the nozzle lifts clear and returns safely to the chute before performing four back-and-forth finishing cycles at commanded 200 mm/s
- **AND** waste-release positioning completes before leveling
- **AND** unavailable vendor cleanup objects are not called

#### Scenario: Optimized cleanup uses fast non-extruding silicone wipes
- **WHEN** retained-filament startup, non-start purge cleanup, unload cleanup, or staged end cleanup reaches an existing silicone-wiper pass
- **THEN** it retains four back-and-forth finishing cycles at commanded 200 mm/s and its existing exit motion
- **AND** no mixed-speed pre-scrape pattern is substituted into these unrelated cleanup paths

#### Scenario: Wipe motion preserves state and unrelated cleanup
- **WHEN** either optimized wipe pattern executes with the nozzle already positioned at the rear wiper
- **THEN** it preserves caller motion and extrusion modes, feed settings, and acceleration
- **AND** the wipe itself performs no extrusion, Y/Z repositioning, heater changes, fixed dwell, or bed scraping
- **AND** retained-filament startup, non-start purge cleanup, manual loading, unload cleanup, staged end cleanup, vendor cleanup commands, and slicer filament-change sequences retain their existing behavior
- **AND** retained-filament startup does not gain a rear-bed scrape or post-scrape sequence

#### Scenario: End-print performs staged cooldown safely
- **WHEN** normal slicer end G-code runs
- **THEN** the toolhead reaches the chute, filament preparation and heater shutdown occur, and staged cooling and wiping complete before print end
- **AND** bed lowering follows the shared slicer rule
- **AND** delayed fan shutdown cannot turn off a fan used by a new or paused print
- **AND** OrcaSlicer may apply configured completion exhaust while QIDI Studio passes zero and omits unsupported indexed completion-air placeholders

#### Scenario: Error cancellation is motion-free
- **WHEN** optimized error cancellation executes
- **THEN** heaters, fans, optional Box heat, pause state, and print state are cleaned up before base cancellation
- **AND** no parking, wiping, or other toolhead motion occurs

#### Scenario: Operator helpers remain guarded and available
- **WHEN** optimized macros load
- **THEN** supported bed-screw, probe-accuracy, Box-temperature, mapping-reset, and startup reporting helpers are available
- **AND** each helper validates required printer state and hardware bounds before acting

### Requirement: Firmware and vendor compatibility surfaces
Optimized configuration SHALL preserve firmware-scoped peripheral ownership, stock integration names, and fan-failure safety while applying guarded hardware optimizations.

#### Scenario: Polar cooler ownership remains firmware-compatible
- **WHEN** firmware uses the direct polar-cooler output
- **THEN** optimized pause and resume do not change its state or recreate removed smart-pin objects
- **AND** existing direct control remains available to approved start, cooling, end, and cancellation paths

#### Scenario: Hotend fan sampling preserves protection
- **WHEN** the supported hotend-fan baseline is installed
- **THEN** the guarded polling interval declared by the package retains sampling margin above measured fan speed
- **AND** fan output, RPM reporting, and zero-RPM shutdown behavior remain unchanged
- **AND** uninstall restores the owned firmware preimage while preserving user drift

#### Scenario: Electronics temperatures are exposed without modifying Fluidd
- **WHEN** optimized configuration is installed
- **THEN** Moonraker and Fluidd receive temperature sensors named `AP_Board_SOC`, `Toolhead_MCU`, and `Mainboard_MCU`
- **AND** the AP-board sensor reads the Linux SoC thermal zone
- **AND** the toolhead sensor reads the THR MCU internal sensor
- **AND** the confirmed GD32F425 mainboard uses the datasheet's uncalibrated typical conversion instead of Klipper's incompatible STM32F407 calibration path
- **AND** the approximate mainboard sensor is observational and uses broad bounds so normal readings do not trigger a machine shutdown

#### Scenario: Stock integration surfaces remain intact
- **WHEN** optimized configuration is installed
- **THEN** stock-named macros required by QIDI software remain available
- **AND** the active vendor Box stack and vendor command names are not redefined
- **AND** `config/fluidd.cfg` and unproven externally consumed stock globals remain unmodified

### Requirement: Load-cell pressure-advance calibration remains fail-closed until validated
The optimized configuration SHALL reserve an operator-invokable load-cell pressure-advance calibration interface without enabling physical calibration or candidate reporting before Max 4 hardware validation is complete.

#### Scenario: Explicit calibration inputs are required
- **WHEN** `TLTG_PA_CALIBRATE` is invoked
- **THEN** `TEMP=<celsius>` and `NOZZLE=<0.2|0.4|0.6|0.8>` are required
- **AND** no temperature or nozzle default is selected implicitly

#### Scenario: Unvalidated calibration has no physical effects
- **WHEN** the required inputs are valid but hardware validation is incomplete
- **THEN** the command reports `PA_CALIBRATION_UNVALIDATED`
- **AND** it returns before homing, heating, movement, sensor acquisition, extrusion, pressure-advance changes, or filament-source changes

#### Scenario: Candidate output is non-persistent
- **WHEN** future hardware validation enables candidate reporting
- **THEN** the result is reported without changing active or persistent pressure advance
- **AND** no slicer, saved-variable, or printer configuration is modified
- **AND** implementation remains in `installer/klipper/tltg-optimized-macros/pa_calibration.cfg` and `installer/klipper/extras/tltg_pa_calibration.py`

### Requirement: Optional staggered print-start heating
Optimized configuration SHALL provide a default-disabled print-start mode that orders requested heater warm-up as bed, chamber, then nozzle, applies a configurable non-negative dwell between active stages, and preserves the existing start entrypoint for previously installed slicer G-code.

#### Scenario: Default startup behavior remains compatible
- **WHEN** staggered heating is disabled or not configured
- **THEN** the established concurrent print-start heating behavior remains active
- **AND** target-bearing and prior no-argument start invocations both continue through homing and filament preparation without requiring a slicer profile migration

#### Scenario: Target-bearing start uses ordered heating
- **WHEN** staggered heating is enabled and the start entrypoint receives bed and chamber targets
- **THEN** the requested bed reaches its startup wait threshold and the configured dwell completes before requested chamber heating begins
- **AND** the requested chamber reaches its startup wait threshold and the configured dwell completes before nozzle heating begins
- **AND** the inter-stage dwell defaults to 10 seconds
- **AND** saved enablement and dwell overrides survive optimized installer updates
- **AND** homing and subsequent print preparation retain their established probing-temperature and safety behavior

#### Scenario: Zero dwell retains ordered activation
- **WHEN** staggered heating is enabled and the inter-stage dwell is configured to zero
- **THEN** no fixed inter-stage delay is added
- **AND** each requested heater still reaches its startup wait threshold before the next heater is activated

#### Scenario: Prior slicer G-code uses active targets
- **WHEN** staggered heating is enabled and prior slicer G-code establishes bed and chamber targets before invoking the start entrypoint without temperature arguments
- **THEN** the optimized start derives the requested stages from the active targets
- **AND** assumes ordered heater control without rejecting the prior invocation

#### Scenario: Unrequested heater stages are skipped
- **WHEN** staggered heating is enabled and the bed or chamber target is zero or its heater is unavailable
- **THEN** that stage is skipped without waiting
- **AND** the remaining requested stages retain bed-before-chamber-before-nozzle order
