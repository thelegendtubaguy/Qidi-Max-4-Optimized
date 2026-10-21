## 1. Implementation

- [x] 1.1 Add `_OPTIMIZED_CHUTE_DROP` and `OPTIMIZED_WIPE_NOZZLE_DROP` to the optimized filament macros.
- [x] 1.2 Replace every optimized wipe-plus-`CLEAR_FLUSH` pair, keeping wipe patterns, stages, and guards.
- [x] 1.3 Update the start-print contract, regenerate its views, and update macro integration coverage, including a check that optimized macros and slicer packs never call `CLEAR_FLUSH` or `CLEAR_OOZE`.
- [x] 1.4 Record `.07.01` chute-cleanup evidence in the QIDI Box observations.
- [x] 1.5 Detect slicer filament changes from print state, revert the unpublished `TOOLCHANGE=1` slicer edit, and skip the filament-change chute move when the vendor tool-change flow owns the cut.
- [x] 1.6 Bump the package version and add release notes.

## 2. Verification

- [x] 2.1 Install on the printer and confirm a fresh Box start, a retained-filament start, and an end-print cleanup each wipe, leave the chute, and re-enter it with waste released.
  - Operator confirmed 2026-10-19: a multi-color Box print on `.07.01` with the chute-drop macros completed; filament changes and wiping looked good. A retained-filament start was not separately exercised.
- [ ] 2.2 On `01.01.07.01`, confirm a slicer filament change goes from the print straight to the cutter, cuts, and then visits the chute once.
