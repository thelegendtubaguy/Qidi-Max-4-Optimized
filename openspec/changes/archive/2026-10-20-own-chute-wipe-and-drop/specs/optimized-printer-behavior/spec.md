## MODIFIED Requirements

### Requirement: Safe print transitions and helpers
Optimized cut, purge, cooldown, cleaning, calibration, and cancellation helpers SHALL preserve caller state, guard optional hardware, and avoid delayed or error-path actions that can affect a subsequent print. Print-start cleaning SHALL preserve staged cooldown wiping with mixed-speed pre-scrape motion and use fast finishing after the cooled rear-bed scrape, with detailed motion and branch ordering controlled by `openspec/contracts/gcode-paths/start-print.path.json`. Chute wipes SHALL release waste with package-owned motion rather than vendor cleanup commands.

#### Scenario: Cut and cleanup preserve caller state
- **WHEN** optimized cut, purge, chute, chamber, or Box-heater helpers run
- **THEN** motion modes, extrusion modes, and temporary acceleration are restored
- **AND** optional Box objects are called only when available and valid
- **AND** fixed waits are reduced without replacing required motion completion waits

#### Scenario: Slicer filament change avoids a double cut on every firmware
- **WHEN** an optimized slicer filament change runs
- **THEN** exactly one cut occurs: the optimized cut when the vendor tool-change flow is absent, or the vendor flow's cut when it is present
- **AND** when the vendor flow is present, the toolhead goes from the print to the cutter without first visiting the chute; the vendor flow moves to the chute after cutting
- **AND** the optimized macros recognize a slicer filament change from print state, so slicer G-code passes no tool-change parameter
- **AND** the same slicer G-code remains correct with older supported firmware

#### Scenario: Optimized cut keeps the vendor reliability sequence
- **WHEN** the optimized filament cut or the stock-named cutter macro used by vendor flows runs
- **THEN** the extruder stepper is released and allowed to settle before the cutter strike
- **AND** the cutter approach, strike, and post-cut retraction match the newest supported stock cut sequence
- **AND** only the stock idle dwell after the toolhead leaves the cutter is omitted
- **AND** the stock-named cutter macro leaves the same modal state as stock for vendor callers

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

#### Scenario: Chute waste release does not depend on vendor cleanup commands
- **WHEN** an optimized chute wipe finishes
- **THEN** the toolhead leaves the chute and re-enters it at the trash position so the waste drops
- **AND** vendor `CLEAR_FLUSH` and `CLEAR_OOZE` are not called, so the release still happens on firmware that removes them
- **AND** caller motion modes and acceleration are restored

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
