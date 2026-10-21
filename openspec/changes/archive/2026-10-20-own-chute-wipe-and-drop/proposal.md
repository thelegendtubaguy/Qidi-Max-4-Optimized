## Why

Every optimized chute wipe finishes with vendor `CLEAR_FLUSH` to leave the chute and re-enter it so the waste drops. QIDI firmware `01.01.07.01` moved its own chute cleanup into editable `DROP_TRASH` and `WIPE_NOZZLE_DROP` macros; its tool-change flow binaries no longer call `CLEAR_FLUSH` or `CLEAR_OOZE`, which survive only in `box_extras`. A later firmware can drop them, and QIDI's firmware silently ignores unknown commands, so the optimized waste release would disappear without an error.

On `01.01.07.01`, optimized slicer filament changes also send the toolhead to the chute before QIDI's tool-change flow drives it to the cutter, cuts, and returns to the chute itself. The first chute visit is wasted travel.

## What Changes

- Add package-owned `OPTIMIZED_WIPE_NOZZLE_DROP`, which runs the existing fast silicone wipe (or the print-start mixed-speed wipe with `PATTERN=MIXED`) and then releases waste with package-owned motion.
- Release waste the way `CLEAR_FLUSH` did (move to X180, then return to the trash position, which leaves and re-enters the chute), but through `OPTIMIZED_MOVE_TO_TRASH` with its faster final approach, and restore caller motion state and acceleration.
- Replace every optimized wipe-plus-`CLEAR_FLUSH` pair with the new macro. Wipe patterns, stage counts, temperature gates, and Box-availability guards are unchanged.
- Keep the published slicer `change_filament.gcode` unchanged (the unpublished `TOOLCHANGE=1` edit is reverted). `26.10.19.1` skipped the optimized cut only when the slicer passed `TOOLCHANGE=1`, which published packs never send, so `01.01.07.01` cut twice. `OPTIMIZED_CUT_FILAMENT` now defers to the vendor `T_MANAGER` flow whenever a print is running, since only slicer filament changes call it during a print; manual cuts while idle or paused still cut.
- When `OPTIMIZED_CUT_FILAMENT` defers to the vendor flow, it records a handoff, and the next `OPTIMIZED_MOVE_TO_TRASH` within 2 seconds of print time skips its move and clears the handoff. On older firmware no handoff is recorded. The vendor cut (`CUT_FILAMENT_1`) already approaches the cutter along Y to Y0 at X≥15 and then along X, so no diagonal cutter approach is introduced.
- Do not redefine vendor `CLEAR_FLUSH`, `CLEAR_OOZE`, `DROP_TRASH`, or `WIPE_NOZZLE_DROP`; vendor flows keep their own cleanup.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `optimized-printer-behavior`: chute waste release uses package-owned motion instead of vendor cleanup commands.

## Impact

- `installer/klipper/tltg-optimized-macros/filament.cfg`, `motion.cfg`, and macro integration coverage.
- `openspec/contracts/gcode-paths/start-print.path.json` and generated views.
- `openspec/observations/qidi-box/hardware-and-protocols.md` for `.07.01` chute-cleanup evidence.
- Package version, aligned macro version, and changelog. No published slicer G-code, firmware snapshot, or upgrade-source metadata changes.
