## 0. Mechanism decision

- [x] 0.1 Confirm, with a log-only wrapper during a vendor load, that `box_extras.get_value_by_key` reads saved variables and which keys and defaults each load and unload stage uses.
- [x] 0.2 Confirm that `box_extras.get_value_by_key` can be wrapped and that loads call the wrapper.
- [x] 0.3 Confirm that wrappers on the three-stage load and two-stage unload methods are called, record their arguments, and show that replacing those arguments changes motion.
- [x] 0.4 Record the results in QIDI Box observations, choose the mechanism, and update `design.md`.

## 1. Implementation

- [x] 1.1 Add the packaged Klipper extra that wraps `do_home_three_steps` and `do_home_double_steps` per slot, guarded by method, argument-shape, and plausibility checks.
- [x] 1.2 Implement settings parsing, per-value bounds, the fast-distance-to-stage mapping, and whole-profile validation with fallback and report.
- [x] 1.3 Apply the configured fast distance as set. A per-slot recorded-distance gate was built, verified, and then removed at the operator's request.
- [x] 1.4 Add `TLTG_BOX_MOTION` to show the effective profile and any vendor-named motion keys, and to set validated values.
- [x] 1.5 Wire the extra into `installer/package.yaml` and add the `installer-lifecycle` delta for package-owned extra modules.
- [x] 1.6 Update the topology-and-control integration boundary, `README.md`, and `CHANGELOG.md` under the unreleased `26.10.23.2`.

## 2. Verification

- [x] 2.1 Installer core tests and the bundle smoke test pass, including the new module lifecycle.
- [x] 2.2 With no settings saved, a vendor load and unload match the baseline arguments and timing.
- [x] 2.3 With settings saved, manual loads and unloads run at the configured speeds without a `QDE_004_*` error.
- [x] 2.8 A multi-color print with tool changes runs at the configured speeds without a `QDE_004_*` error.
- [x] 2.4 A fast distance longer than the vendor's applies on the next load (verified at 957 mm on slot 2 under the removed gate; the direct path is covered by the module harness).
- [x] 2.5 An infeasible profile, such as equal unload speeds or fast stage speeds whose speed changes don't fit in stage 2, falls back to vendor motion with a report.
- [x] 2.6 Unexpected vendor calls pass through unchanged with a report (module harness).

## 3. Per-slot settings and published status

- [x] 3.1 Add per-slot override variables, `SLOT=` handling in `TLTG_BOX_MOTION`, per-slot profile resolution and validation, and validation of overridden slots before saving a global change.
- [x] 3.2 Add a cached `get_status()` with the schema in `design.md`.
- [x] 3.3 Verify on the printer that `tltg_box_feed_motion` is listed and subscribable, and that a slot override changes only that slot's load.

## 4. Fluidd panel

- [x] 4.1 Add the guarded Box motion step to `installer/runtime/fluidd_box_filaments.py`, rendering the section at the end of Box Config.
- [x] 4.2 Implement the global form, per-slot rows and editing, inline command errors, and busy and inactive states.
- [x] 4.3 Extend the Fluidd fixtures and the existing lifecycle test, and check a fully patched real bundle with `node --check`.
- [x] 4.4 Check the panel in a browser against the printer.

## 5. Documentation

- [x] 5.1 Update `README.md` and `CHANGELOG.md` for per-slot settings and the Fluidd panel.

## 6. Extruder retract

- [x] 6.1 Add the global-only `UNLOAD_EXTRUDER_LENGTH` setting for the vendor's second extruder retract, through the `exl_2` lookup, with status and panel field.
- [x] 6.2 Verify on the printer that an unload uses the configured length.

## 7. Release defaults and panel lock

- [x] 7.1 Save the release motion profile on install, update, and idle repair when no motion setting exists, preserving any operator value including `None`.
- [x] 7.2 Lock panel editing only while printing or when Klipper's live state isn't ready.
- [x] 7.3 Confirm in the browser that the panel stays editable after a load, unload, and Klipper restart.
