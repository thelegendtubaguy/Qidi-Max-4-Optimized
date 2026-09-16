# installer-lifecycle Specification

## Purpose

The installer admits supported QIDI firmware, changes only validated installer-owned state, and keeps install, update, restore, and uninstall recoverable.

## Requirements

### Requirement: Firmware-gated ownership
The installer SHALL select one complete baseline for the detected supported firmware and change only recognized stock state or state proven to be installer-owned.

#### Scenario: Supported firmware selects one baseline
- **WHEN** installation starts on firmware declared in `installer/package.yaml`
- **THEN** exactly one complete firmware-scoped variant is selected for every required target
- **AND** configuration and managed-source expectations come from that baseline

#### Scenario: Invalid admission fails before unsafe work
- **WHEN** firmware is unreadable or unsupported
- **THEN** the operation fails before reading installed state, creating a backup, or writing live files
- **AND** incomplete or ambiguous baseline data or an unclassifiable managed target fails before backup or mutation
- **AND** unowned live content is preserved

#### Scenario: Legacy installation is migrated conservatively
- **WHEN** legacy optimized markers exist without valid installer state
- **THEN** migration requires an idle printer and a validated stock snapshot for the detected firmware
- **AND** vendor-managed, user-specific, and sensitive configuration remains preserved

### Requirement: Recoverable configuration lifecycle
Install, reinstall, restore, and uninstall SHALL execute as serialized, idle-printer transactions with validated inputs, recoverable preimages, atomic committed state, and drift-safe reversal.

#### Scenario: Mutation begins only after complete preflight
- **WHEN** a mutating operation starts
- **THEN** it validates printer state, prior state, targets, paths, bundle contents, and required storage before backup or writes
- **AND** printing, paused, unknown, malformed, concurrent, or recovery-blocked state fails closed

#### Scenario: Installation commits atomically
- **WHEN** installation changes validated targets
- **THEN** a configuration backup and recoverable preimages are created automatically before the first write without requesting installation confirmation
- **AND** the managed tree and guarded patches converge to the selected release
- **AND** installed state is committed only after postflight verifies the resulting files and ownership ledger
- **AND** failure restores preimages or records a recovery blocker when compensation cannot complete

#### Scenario: Uninstall respects ownership
- **WHEN** uninstall processes a valid ownership ledger
- **THEN** only unchanged installer-owned state is reverted
- **AND** user-modified state is preserved and reported
- **AND** installed state is removed only after successful postflight

#### Scenario: Restore reconstructs the archived runtime
- **WHEN** restore receives explicit confirmation for a validated installer archive
- **THEN** it validates printer idleness after confirmation and before replacing live runtime state, including for config-only archives
- **AND** printing, paused, unknown, or unavailable printer state prevents live replacement
- **AND** archived configuration and eligible external members are staged before replacing live runtime state
- **AND** partial failure restores the pre-restore state
- **AND** every restored root is verified before success and recovery remains blocked until incomplete compensation is resolved

#### Scenario: Non-mutating and interrupted runs remain safe
- **WHEN** dry-run, help, demo, alternate reporting, or interruption is selected
- **THEN** safety decisions remain equivalent to the normal flow
- **AND** no unapproved backup, pruning, or live mutation occurs
- **AND** interruption prevents later actions and exits without a traceback
- **AND** interruption after an uncommitted configuration write restores recoverable preimages or records a recovery blocker if compensation cannot complete
- **AND** interruption after configuration commit preserves the verified result and any outstanding activation or host-recovery obligation without reporting unfinished work as complete
- **AND** compensation does not restore a whole vendor saved-variable file over live Klipper state

#### Scenario: Preview and execution agree on file changes
- **WHEN** install or uninstall evaluates the same validated files, release, and operator policy
- **THEN** dry-run reports the same proposed file changes and preserved drift as execution
- **AND** execution rejects changed preimages before overwriting them rather than silently applying a stale decision
- **AND** live runtime interactions retain their own readiness, idleness, and authorization checks

### Requirement: Managed Klipper source activation
The installer SHALL deploy firmware-scoped Klipper source only from validated provenance and consider a source change active only after a replacement Klipper process is verified ready.

#### Scenario: Managed source deployment is provenance-bound
- **WHEN** a managed source target matches selected stock content or valid prior-managed state
- **THEN** its original bytes and metadata are retained before atomic deployment
- **AND** the payload is verified against the selected release before installed state commits
- **AND** unknown, escaped, symlinked, tampered, or cross-firmware provenance fails before mutation

#### Scenario: Source restoration preserves drift
- **WHEN** rollback, restore, or uninstall processes managed source
- **THEN** unchanged installer-owned content may return to its retained preimage
- **AND** content already at the preimage is unchanged
- **AND** any other live content is preserved and reported as drift

#### Scenario: Project-owned external Python is provenance-bound
- **WHEN** installation manages a project-owned Klipper extra that has no stock baseline
- **THEN** its ID and destination are unique across source patches and external files
- **AND** its bundle source is a non-symlink regular file under `installer/klipper/` whose SHA-256 matches the manifest
- **AND** its destination is a relative non-traversing path under `klippy/extras/`
- **AND** the ledger's package identity and version must be admitted, and prior installed hashes are accepted only when enumerated for the same ID and destination in the cumulative compatibility envelope
- **AND** unknown, escaped, symlinked, tampered, or unowned live content fails before mutation

#### Scenario: External-file deployment is transactional
- **WHEN** a new or previously managed external Python file changes
- **THEN** pending activation is recorded before atomic replacement
- **AND** installed state records the installed hash and any validated preimage bytes, hash, and mode
- **AND** failure restores the preimage or removes the newly created target before state commits

#### Scenario: External-file uninstall and restore preserve ownership
- **WHEN** uninstall or archive restore processes a managed external Python file
- **THEN** install and uninstall backups capture each state-owned external Python payload with its destination, hash, and mode
- **AND** uninstall removes only content matching the installed hash or restores its validated preimage
- **AND** archive restore reconstructs declared presence only from archived bytes matching the provenance-validated installed hash
- **AND** archived state that omits the external file requires the managed payload to be absent
- **AND** unknown live drift is preserved and blocks mutation

#### Scenario: Activation requires a replacement process
- **WHEN** managed source changes or pending source activation exists
- **THEN** activation remains pending until Klipper becomes ready under a different valid process identity
- **AND** source-changing install and uninstall operations automatically restart Klipper after a fresh idle-state check without requesting separate confirmation
- **AND** restart verification allows at least 60 seconds for Klipper to become ready under the replacement process identity
- **AND** active, unknown, failed, or drifted activation remains pending and blocks unsafe continuation
- **AND** the pending marker binds each source patch and external Python destination to its intended live hash or expected absence
- **AND** every installer entrypoint resolves pending activation before further release work
- **AND** a post-activation saved-variable mismatch retains its exact authorized expectations and blocks later install or automatic-update work until an exact live Moonraker verification succeeds; dry-run verification preserves the marker, and terminal uninstall removes it only after successful postflight while rollback preserves it


### Requirement: Non-owning QIDI Box reconciliation
The installer SHALL keep an available QIDI Box usable without claiming ownership of vendor saved variables or silently replacing existing non-empty tool mappings.

#### Scenario: Optional Box state is reconciled conservatively
- **WHEN** the Box stack is available
- **THEN** explicit interactive or `--yes` policy may enable it
- **AND** missing active mappings are created as identity mappings
- **AND** existing non-empty mappings change only after explicit interactive approval

#### Scenario: Automatic reconciliation preserves vendor state
- **WHEN** noninteractive install or update observes Box topology while the printer is idle
- **THEN** missing active mappings are created and existing non-empty mappings are preserved
- **AND** busy, unavailable, or not-ready Klipper state causes no reconciliation writes
- **AND** every write uses Klipper's live `SAVE_VARIABLE` command through Moonraker, verifies its live value and, when a source-patch restart occurs, verifies it again after the replacement process; it never restores a whole saved-variable file during rollback
- **AND** saved-variable changes are excluded from installer ownership and uninstall

### Requirement: Default optimized preferences preserve operator values
The installer SHALL initialize absent optimized saved-variable preferences to release defaults without replacing operator-controlled values.

#### Scenario: Absent retention preference receives the installed default
- **WHEN** install or update finds no `tltg_keep_loaded_between_prints` entry in Klipper saved variables
- **THEN** it saves `1` through Moonraker only after Klipper is ready, verifies the live value and, when a source-patch restart occurs, verifies it again after the replacement process; existing `0` is preserved as an operator choice
- **AND** install and upgrade repair missing defaults while idle; already-current automatic-update checks perform this repair only on enrolled printers
- **AND** the preference remains outside the installed-state ownership ledger

#### Scenario: Existing retention preference is preserved
- **WHEN** install or update finds an existing `tltg_keep_loaded_between_prints` value, including `0`
- **THEN** it leaves that value unchanged
- **AND** uninstall does not remove or reset it

### Requirement: Opt-in recoverable host optimization
The installer SHALL apply host OS optimizations only under explicit persisted policy, preserve recoverable preimages, and keep host-operation failures separate from a verified printer-configuration result. System optimizations SHALL remain available through the same packaged install, update, and uninstall flow without requiring a separate package or operator command.

#### Scenario: Enabled policy reconciles only recognized host state
- **WHEN** system optimizations are enabled
- **THEN** each declared operation validates its live preconditions before mutation
- **AND** installer-owned drift is reconciled without replacing first restore preimages
- **AND** unowned, unknown, or user-modified state is preserved and reported
- **AND** operation failure rolls back journaled host work without deleting a verified configuration install
- **AND** incomplete host compensation retains a recovery blocker and does not report the overall operation as complete

#### Scenario: Uninstall follows the operator's host-state decision
- **WHEN** uninstall finds host restore preimages
- **THEN** accepted restoration reverts only unchanged installer-owned targets
- **AND** targets already at their retained preimages are left unchanged
- **AND** user-modified files, symlinks, assets, or service states are preserved and reported
- **AND** declined restoration or explicit keep policy leaves current host state unchanged

#### Scenario: Reconciliation retains bounded recovery state
- **WHEN** repeated checks find host optimizations already current
- **THEN** installer recovery-state size and restoration-backup count do not grow with the number of checks
- **AND** first restoration preimages and unresolved transaction or reboot evidence remain available
- **AND** previously installed host ledgers remain recoverable when their historical action records are compacted

#### Scenario: Host reboot is deferred until safe
- **WHEN** an applied operation requires a host reboot
- **THEN** the requirement is persisted without embedding executable commands
- **AND** reboot is scheduled only after successful transaction completion, explicit authorization, and a fresh idle-printer check
- **AND** later execution clears the requirement only after post-boot verification succeeds
- **AND** dry-run, active, or unknown printer state performs no reboot

### Requirement: Recoverable Moonraker metadata optimization
Normal install and update SHALL apply recognized Moonraker metadata optimizations independently of optional OS optimization policy, retain original source preimages, and preserve unrecognized or operator-modified source.

#### Scenario: Multi-plate 3MF metadata follows the selected plate
- **WHEN** the optimized metadata extractor reads a `.gcode.3mf` archive
- **THEN** G-code, metadata, and thumbnail selection use its valid selected plate index
- **AND** missing or invalid plate metadata falls back to plate 1

#### Scenario: Unchanged archives reuse persistent metadata
- **WHEN** startup observation or upload handling encounters a 3MF with cached metadata matching its size, modification time, extractor stamp, and object-processing policy
- **THEN** extraction is skipped without changing cached thumbnails or last-printed fields
- **AND** new, changed, unstamped, or invalidated archives remain eligible for extraction
- **AND** an unavailable extractor never validates a cached archive

#### Scenario: Mixed metadata requests complete without a stuck queue
- **WHEN** G-code and 3MF requests share a pending metadata queue
- **THEN** both entrypoints use the same cache-aware worker
- **AND** a request that becomes valid while queued is removed and its waiter released
- **AND** exhausting extraction retries is not treated as a successful metadata refresh and does not prevent later requests from completing

#### Scenario: Manual 3MF rescans use archive-aware extraction
- **WHEN** an operator requests a metadata rescan for a 3MF within the G-code root
- **THEN** the archive is explicitly re-extracted through the shared metadata queue, or the request joins extraction already pending for that archive
- **AND** existing QIDI thumbnail files are not deleted
- **AND** extraction failure returns an error and preserves prior metadata
- **AND** escaped, reserved, and missing archive paths are rejected before extraction
- **AND** ordinary G-code rescan behavior remains unchanged

#### Scenario: File-manager deployment remains reversible
- **WHEN** recognized file-manager source requires the cache patch
- **THEN** the installer validates the reviewed metadata class and metascan handler before backup, preserves unrelated source and line endings, and replaces the file atomically
- **AND** source changes require a successful Moonraker restart; restart failure compensates the file change or retains a recovery blocker
- **AND** repeated reconciliation retains the first restore preimage without accumulating backups
- **AND** accepted uninstall restoration reverts only the unchanged installed file; concurrent changes and operator drift are preserved

### Requirement: Safe unattended updates
Automatic updates SHALL require durable operator enrollment, use the same admission, ownership, recovery, activation, and persisted host-policy rules as direct installation, and advance release state only after successful activation.

#### Scenario: Enrolled release installation is idle and integrity checked
- **WHEN** an enrolled updater observes a new release checksum or missing or drifted optimized installation state
- **THEN** update proceeds only while the printer is idle and after archive integrity and path safety are verified
- **AND** missing or drifted state runs the current release installer even when its checksum is unchanged
- **AND** durable enrollment may re-adopt an untracked external Python target only when its bytes exactly match the current manifest payload
- **AND** the bundled noninteractive installer performs the change
- **AND** release state advances only after install and required Klipper activation succeed
- **AND** any host reboot is considered only after that state is durable and printer idleness is revalidated

#### Scenario: No-op and failure paths preserve release state
- **WHEN** release discovery fails, durable enrollment is absent, activation remains pending, or child installation fails
- **THEN** no release is falsely recorded as installed and no reboot is scheduled
- **AND** absent enrollment records the fetched checksum without installing whether checksum state is missing or changed
- **AND** a matching enrolled release reports current only after critical optimized installation state passes verification
- **AND** an already-current release may reconcile enabled installer-owned policy while idle

#### Scenario: Update plumbing is ownership-bound
- **WHEN** automatic updates are enabled, repaired, disabled, or removed during uninstall
- **THEN** only installer-owned scheduling, durable enrollment, and checksum state is created, repaired, or removed
- **AND** successful setup records enrollment outside firmware-cleaned configuration
- **AND** disable or uninstall removes enrollment before privileged timer cleanup so a surviving service cannot install or reconcile
- **AND** plumbing failure is reported separately from successful configuration or uninstall work
