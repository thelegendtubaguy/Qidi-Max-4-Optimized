# Design

## Context

A profile of the core suite shows `run_install` and `run_uninstall` account for most of the run. Fixture copying is minor. The cost per test therefore tracks the number of lifecycle runs it performs.

## Decisions

### Matrices cover inputs that reach different code

Fresh install selects a source-patch variant by firmware and live hash, so it keeps every admitted variant. Restore paths do not select a variant: they compare the live file with the recorded original and desired hashes and write back the recorded bytes. They keep one case from each payload family (standard and sync-reset), which also covers both firmware config groups. Config-ledger migration and auto-update installation do not depend on the source variant and run once.

### Remove a test only when another one checks its invariant end to end

Tests of private helpers or mocked internal call order are removed when a lifecycle test reaches the same outcome through real inputs. Tests of distinct safety boundaries stay even when slow, including forged ledgers and journals, interruption recovery, operator-drift preservation, and legacy migration.

## Non-Goals

- Changing installer runtime code, persistence, or the test runner.
- Sharing mutable fixtures between tests.
