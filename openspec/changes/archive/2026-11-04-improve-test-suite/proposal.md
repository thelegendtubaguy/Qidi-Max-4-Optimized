# Proposal

## Why

`python3 scripts/run_installer_core_tests.py` took 7.5–8.1 s, over the repository's six-second target. Nearly all of the time is full install, update, and uninstall runs, and several tests repeat those runs across inputs that do not reach different code.

## What Changes

- Run the historical-version update and uninstall scenario once, from the oldest version, instead of for five versions. Version admission for every version is already checked directly.
- Keep the fresh-install source-patch matrix across every admitted firmware/source variant. Run uninstall, backup restore, and write-failure rollback for one standard and one sync-reset variant, and run prior-value migration and auto-update installation once. Source restoration writes back the recorded preimage whatever the variant.
- Remove two tests whose invariant another test already checks end to end: a private drift-detection helper test, covered by the `already-current` and `reconciled` auto-update outcomes, and a mocked invalid-uninstall-plan test, covered by forged-ledger uninstall rejection.
- Copy only the files the version-bump script reads, and drop an unused fixture setup.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Only tests change; requirements and installed behavior do not.

## Impact

`installer/tests/` only. Tests are not part of the release bundle, so no package version change is needed.
