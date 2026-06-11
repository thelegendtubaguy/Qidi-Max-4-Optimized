## Why

QIDI Max 4 firmware `01.01.06.04` ships stock config changes that affect closed-loop X/Y motor parameters, pause/resume/cancel cleanup, idle pause recovery, filament naming, QIDI Box runout handling, and chamber thermal protection. The installer currently supports only firmware `01.01.06.03`, so `.04` printers are blocked and `.03`-specific assumptions must remain guarded.

## What Changes

- Add installer support for firmware `01.01.06.04` while retaining support for `01.01.06.03`.
- Apply `.03` stock-baseline expectations only when detected firmware is `01.01.06.03`.
- Apply `.04` stock-baseline expectations only when detected firmware is `01.01.06.04`.
- Carry QIDI `.04` stock deltas into the stock-mapped config baseline and installer guarded patch variants.
- Ensure legacy manual-install reset restores the correct stock snapshot for the detected firmware instead of applying one firmware baseline to all printers.
- Preserve existing optimized behavior unless a `.04` stock change must be represented for firmware compatibility.

## Capabilities

### New Capabilities
- `firmware-baseline-support`: Installer detection, stock snapshot selection, and guarded patch behavior across supported QIDI firmware baselines.

### Modified Capabilities

## Impact

- `installer/package.yaml` firmware support and patch variants.
- `installer/stock/qidi-max4-defaults/` stock snapshot layout and legacy reset runtime selection.
- `installer/runtime/legacy_manual_install.py` stock restore path resolution.
- Stock-mapped files under `config/` for `.04` baseline alignment where approved.
- Installer validation scripts and tests covering `.03` and `.04` manifests.
- Documentation under `docs/` for installer runtime behavior and firmware baseline handling.
