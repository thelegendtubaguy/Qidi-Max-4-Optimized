## Context

`installer/package.yaml firmware.supported` currently lists only `01.01.06.03`. Existing guarded optimization patch targets provide one variant for every supported firmware, while `.04`-only stock-baseline targets must be active only for `.04` so `.03` configs do not require new vendor options. The installer also ships a single stock snapshot at `installer/stock/qidi-max4-defaults/config/`, and `installer/runtime/legacy_manual_install.py` restores that snapshot during legacy manual-install reset.

QIDI firmware `01.01.06.04` changes stock files in `thelegendtubaguy/Qidi-Max4-Defaults` commit `5da5767379ac22fc4fbe1606ec7093ce056229ae`:

- `config/printer.cfg`: QIDI Box runout guard, X/Y closed-loop `query_cycle:10`, new X/Y `trigger_current`, `trigger_time`, `trigger_speed`, and `Chamber_Thermal_Protection_Sensor max_temp:170`.
- `config/klipper-macros-qd/idle.cfg`: idle pause temperature save target changes from `resume` to `RESUME_PRINT`.
- `config/klipper-macros-qd/pause_resume_cancel.cfg`: optional pause wipe, resume wipe, and delayed `_KM_CANCEL_PRINT_BASE` call.
- `config/officiall_filas_list.cfg`: `PA-CF` entry renamed to `PA6-CF`.

`config/` is stock-mapped. Stock baseline changes belong in guarded installer patch variants unless a direct stock snapshot update is required for legacy reset or repo baseline traceability.

## Goals / Non-Goals

**Goals:**

- Support installer runs on detected firmware `01.01.06.03` and `01.01.06.04`.
- Preserve `.03` expected stock values and guarded patch behavior when detected firmware is `.03`.
- Use `.04` expected stock values and guarded patch behavior when detected firmware is `.04`.
- Restore firmware-matched stock files during legacy manual-install reset.
- Keep optimized behavior changes explicit and separately documented.
- Validate manifest coverage for both firmware versions.

**Non-Goals:**

- Do not tune QIDI's `.04` closed-loop values beyond the shipped stock baseline.
- Do not drop support for `01.01.06.03`.
- Do not modify `config/fluidd.cfg`.
- Do not add unredacted hardware identifiers or edit sensitive local identifiers.
- Do not introduce direct polar cooler controls to QIDI Studio G-code.

## Decisions

### Use firmware-specific guarded variants instead of a universal stock baseline

`installer/package.yaml` will list both `01.01.06.03` and `01.01.06.04`. Every existing patch target will get a `.04` variant. Variant expected values will match the detected firmware's stock baseline. Existing optimized X/Y homing speed desired values will remain unchanged for `.04`; hardware testing will verify whether QIDI's new closed-loop trigger settings require a later adjustment.

Alternative considered: update all expected values to `.04` and allow `.03` to fail or be user-modified. Rejected because the installer must keep working on `.03` and manifest validation is explicitly firmware-aware.

### Keep `.04` closed-loop parameters firmware-specific

`.04` adds `trigger_current`, `trigger_time`, and `trigger_speed` beside `query_cycle:10`. These options should be applied only for `.04`; they must not be injected into `.03` because older vendor closed-loop code may reject unknown options.

Alternative considered: add `trigger_*` to both `.03` and `.04` for consistency. Rejected because the compiled QIDI closed-loop module behavior is not guaranteed across firmware versions.

### Treat `=` to `:` formatting as non-semantic

QIDI changed some `[closed_loop x]` delimiters from `=` to `:` while leaving `[closed_loop y]` mostly unchanged. Klipper-style config parsing and the installer parser accept both. Implementation must preserve stock values, but delimiter normalization is not a behavior requirement.

Alternative considered: encode delimiter-specific patch behavior. Rejected because patch matching and application operate on option values, not delimiter spelling.

### Use firmware-specific stock snapshots for legacy reset

Legacy manual-install reset must not restore `.04` stock files onto a `.03` printer or `.03` files onto a `.04` printer. The stock snapshot layout should support one config tree per firmware, and runtime selection should use the detected firmware.

Alternative considered: keep one snapshot at `installer/stock/qidi-max4-defaults/config/`. Rejected because a single tree cannot safely represent both firmware baselines.

### Adopt base-last cancel cleanup ordering in optimized error cancel

`pause_resume_cancel.cfg` remains stock-active unless replaced by optimized overrides. `.04` stock changes should be included for `.04` baseline compatibility. `OPTIMIZED_CANCEL_PRINT_ON_ERROR` will preserve its no-park/no-toolhead-move intent while moving `_KM_CANCEL_PRINT_BASE` after pause-state restore, `G31`, and `CLEAR_PAUSE` to match QIDI's `.04` base-last cleanup ordering.

Alternative considered: leave `OPTIMIZED_CANCEL_PRINT_ON_ERROR` unchanged because it is an error-only path. Rejected because QIDI's stock order change likely addresses cancel finalization/state cleanup ordering, and the same base-last ordering is applicable without adding movement.

### Update PA6-CF references while preserving unchanged drying data

Local docs and tests that assert the official filament list entry for `[fila25]` should use `PA6-CF` for `.04` baseline behavior. `drying.conf` should remain unchanged unless QIDI changes it upstream because `.04` did not rename that drying table entry.

Alternative considered: rename every `PA-CF` occurrence. Rejected because `drying.conf` remains stock `PA-CF` in QIDI's `.04` defaults.

## Risks / Trade-offs

- `.04` `trigger_speed:50` may interact with optimized homing speed patches (`65`) → keep the current optimized homing desired values and validate on hardware before broad release.
- Firmware-specific stock snapshots increase installer bundle size and path complexity → keep snapshot layout deterministic and validate source trees during preflight/tests.
- `.04` stock pause/resume wipe adds motion during resume → document behavior and avoid adding additional optimized motion unless explicitly approved.
- `printer["box_extras"]` guards remain partly unsafe if the object is undefined → prefer defined-safe patterns in optimized macros, but preserve vendor stock behavior unless intentionally patched.
- Raising chamber thermal protection max temp from `150` to `170` reduces false trips but raises the cutoff → treat as stock baseline, not an optimized safety tune.

## Migration Plan

1. Add `.04` firmware support and complete manifest variants.
2. Introduce firmware-specific stock snapshot resolution for legacy reset.
3. Add `.04` stock snapshot content from `../Qidi-Max4-Defaults` at commit `5da5767379ac22fc4fbe1606ec7093ce056229ae` or tag `qidi-max4-firmware-01.01.06.04`.
4. Keep `.03` snapshot content available for `.03` legacy reset.
5. Update docs for installer runtime contract and firmware baseline behavior.
6. Run installer manifest and runtime validation scripts.

## Open Questions

- None.