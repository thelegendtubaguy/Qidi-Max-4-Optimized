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

#### Scenario: Activation requires a replacement process
- **WHEN** managed source changes or pending source activation exists
- **THEN** activation remains pending until Klipper becomes ready under a different valid process identity
- **AND** source-changing install and uninstall operations automatically restart Klipper after a fresh idle-state check without requesting separate confirmation
- **AND** restart verification allows at least 60 seconds for Klipper to become ready under the replacement process identity
- **AND** active, unknown, failed, or drifted activation remains pending and blocks unsafe continuation
- **AND** every installer entrypoint resolves pending activation before further release work
- **AND** a post-activation saved-variable mismatch retains its exact authorized expectations and blocks later install or automatic-update work until an exact live Moonraker verification succeeds; dry-run verification preserves the marker, and terminal uninstall removes it only after successful postflight while rollback preserves it

### Requirement: Managed probe diagnostic helper
Normal install and update SHALL install the bundled Klipper probe diagnostic helper independently of optional OS optimization policy, retaining ownership evidence without replacing unrecognized or operator-modified helper files.

#### Scenario: Helper is installed and activated
- **WHEN** the helper destination is absent
- **THEN** the installer records its absence, creates the bundled helper without overwriting a concurrent file, verifies its contents, and restarts Klipper
- **AND** an unchanged current helper is left alone, while a missing owned helper can be repaired
- **AND** installation does not report successful activation with a missing or modified required helper

#### Scenario: Helper restoration respects ownership
- **WHEN** accepted system restoration during uninstall or host-transaction recovery processes the helper
- **THEN** an unchanged installed helper is removed if it was originally absent, or restored to its retained preimage
- **AND** a modified helper is preserved and reported
- **AND** an incomplete restoration or required service restart retains a recovery blocker

### Requirement: Non-owning QIDI Box reconciliation
The installer SHALL keep an available QIDI Box usable without claiming ownership of vendor saved variables or silently replacing existing non-empty tool mappings. Box availability SHALL be recognized for every supported firmware's Box transport, including the legacy USB Box configuration and the RS-485 Box stack.

#### Scenario: Optional Box state is reconciled conservatively
- **WHEN** the Box stack is available
- **THEN** explicit interactive or `--yes` policy may enable it
- **AND** missing active mappings are created as identity mappings
- **AND** existing non-empty mappings change only after explicit interactive approval

#### Scenario: Box availability is transport-independent
- **WHEN** a QIDI Box is attached through either the legacy USB configuration or the RS-485 Box stack
- **THEN** Box enablement and tool-mapping reconciliation treat the Box as available
- **AND** a printer with no attached Box is not treated as Box-capable solely because firmware always loads Box controller objects

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

### Requirement: Recoverable Fluidd QIDI Box filament display
Normal install and update SHALL patch the recognized QIDI Fluidd bundle so its QIDI Box card displays and edits slots the way QIDI firmware `01.01.07.01` stores and resolves them, independently of optional OS optimization policy, retaining the original bundle and preserving unrecognized or operator-modified bundles.

#### Scenario: Box slots show the firmware's resolved filament
- **WHEN** Fluidd is connected to firmware that exposes `box485` and `multi_color_controller` slot information
- **THEN** each Box slot and the rack show the filament name, vendor, and color the firmware resolved for that slot, including for saved IDs such as `QFA90`, RGB colors such as `["228332"]`, and stale numeric IDs
- **AND** an unknown filament ID displays as its ID

#### Scenario: Box pickers save firmware filament IDs and RGB colors
- **WHEN** an operator edits a slot in Fluidd on that firmware
- **THEN** the vendor picker lists the firmware filament database vendors and the filament picker lists the selected vendor's filaments
- **AND** choosing a filament saves its `QF` ID as a string, choosing a vendor saves that vendor's filament of the current type or its first filament, and choosing a color saves a one-element RGB list
- **AND** `vendor_slotN` is not written

#### Scenario: Box buttons use the firmware's Box commands
- **WHEN** Fluidd is connected to firmware that exposes `multi_color_controller`
- **THEN** the Box card's Eject, Load, Unload, and RFID controls send `EJECT_FILAMENT_CONTROL`, `LOAD_FILAMENT_CONTROL`, `UNLOAD_FILAMENT_CONTROL`, and `READ_RFID` with the selected slot number
- **AND** Load and Unload availability follows the Box path sensor from `box_extras` or, when `box_extras` omits it, from `multi_color_controller`

#### Scenario: Earlier firmware keeps stock pickers
- **WHEN** Fluidd is connected to firmware without `box485`
- **THEN** slots display through `officiall_filas_list.cfg` and the stock pickers save numeric IDs as before
- **AND** without `multi_color_controller`, the Box controls send the stock commands

#### Scenario: Browsers load the patched bundle
- **WHEN** a browser that previously cached Fluidd through its service worker opens Fluidd after the bundle patch changes
- **THEN** the service worker updates and fetches the patched bundle instead of serving the cached one
- **AND** the recognized service worker's bundle precache revision is set from the bundle patch, with the same recognition, preservation, and restoration as the bundle

#### Scenario: Unrecognized Fluidd bundles are preserved
- **WHEN** the configured bundle is missing or does not match the reviewed stock source or an earlier package patch of it
- **THEN** the bundle is left unchanged and the outcome is recorded without failing other host patches

#### Scenario: Fluidd deployment remains reversible
- **WHEN** the recognized bundle requires the patch
- **THEN** the installer backs up the original bytes and replaces the file atomically without restarting services
- **AND** a bundle carrying an earlier package patch is updated in place while the first restore preimage is retained
- **AND** accepted uninstall restoration reverts only the unchanged installed bundle; concurrent changes and operator drift are preserved

### Requirement: QIDI Box heater targets from Fluidd
Normal install and update SHALL patch recognized QIDI Klipper `box_config.py` and the recognized QIDI Fluidd bundle so Fluidd's temperature panel sets QIDI Box heater targets within the Box heater and loaded-filament limits, independently of optional OS optimization policy, retaining original files and preserving unrecognized or operator-modified files.

#### Scenario: Box heater limits reach Fluidd
- **WHEN** Klipper loads the patched `box_config.py`
- **THEN** `configfile.settings` includes each generated `heater_generic heater_boxN` section with its configured temperature limits
- **AND** its `target_max_temp` is the lower of the `box.cfg` value and 65 °C, the Box's advertised maximum
- **AND** other generated Box objects are unchanged

#### Scenario: Loaded filaments limit Box heating
- **WHEN** filament is loaded in any slot of a Box
- **THEN** Fluidd accepts targets up to the lowest Box limit declared by that Box's loaded filaments, including a limit of `0`
- **AND** loaded filaments without a declared limit do not restrict the target, and a Box without restricting filaments accepts targets up to its heater's `target_max_temp`

#### Scenario: Filaments that disallow heating lock the target
- **WHEN** a Box's effective limit is `0`
- **THEN** its target input is disabled
- **AND** a Box with an active nonzero target remains editable so it can be set to `0`

#### Scenario: Box heater deployment remains reversible
- **WHEN** a recognized `box_config.py` requires the patch
- **THEN** the installer backs up the original bytes, preserves line endings, replaces the file atomically, and restarts the Klipper service
- **AND** accepted uninstall restoration reverts only the unchanged installed file and restarts the Klipper service; concurrent changes and operator drift are preserved
- **AND** a missing or unrecognized `box_config.py` is left unchanged and the outcome is recorded without failing other host patches

### Requirement: Klipper shutdown reasons remain visible
Normal install and update SHALL patch recognized QIDI Klipper `print_stats_manager.py` so a Klipper shutdown keeps its original reason instead of ending in a host crash, independently of optional OS optimization policy, retaining the original file and preserving unrecognized or operator-modified files.

#### Scenario: Shutdown during a print keeps its reason
- **WHEN** Klipper shuts down while the QIDI main status is `printing` and later commands are refused
- **THEN** the command-error status reset is skipped, no G-code is issued from it, and Klipper remains running in the shutdown state with the original reason

#### Scenario: Status reset does not re-enter itself
- **WHEN** Klipper is not shut down and a command run by the command-error status reset is itself refused
- **THEN** the nested reset is skipped and the refusal is reported once
- **AND** a later command error while ready resets the status to `ready` and restores the Z drivers' stealthChop threshold as QIDI's module does

#### Scenario: Shutdown-reason deployment remains reversible
- **WHEN** a recognized `print_stats_manager.py` requires the patch
- **THEN** the installer backs up the original bytes, preserves line endings, replaces the file atomically, and restarts the Klipper service
- **AND** accepted uninstall restoration reverts only the unchanged installed file and restarts the Klipper service; concurrent changes and operator drift are preserved
- **AND** a missing or unrecognized `print_stats_manager.py` is left unchanged and the outcome is recorded without failing other host patches

### Requirement: Fluidd full display by default
Normal install and update SHALL patch the recognized QIDI Fluidd bundle so QIDI's "Enable Full Display" setting defaults on, independently of optional OS optimization policy, with the same recognition, preservation, and restoration as the QIDI Box filament display patch.

#### Scenario: Full display is on unless the operator turned it off
- **WHEN** Fluidd loads settings that do not include a saved "Enable Full Display" value
- **THEN** full display is enabled, showing the bed mesh card on the Tune page and target-less temperature sensors in the temperature panel and chart
- **AND** a value saved from Fluidd's settings, including off, still applies

### Requirement: QIDI filament database in Fluidd
Normal install and update SHALL expose QIDI's touchscreen filament database directory as `config/qidi_filament_config` in Fluidd's configuration files, independently of optional OS optimization policy, without copying, backing up, or modifying the database files.

#### Scenario: Link is created where the database exists
- **WHEN** the QIDI filament database directory exists and `config/qidi_filament_config` is absent
- **THEN** the installer creates a symlink to the directory and records ownership for restoration
- **AND** reconciliation recreates an owned link that is absent and leaves a current link unchanged

#### Scenario: Missing databases and existing entries are preserved
- **WHEN** the database directory is missing or `config/qidi_filament_config` already exists as anything other than the installer's link
- **THEN** no link is created, the existing entry is left unchanged, and the outcome is recorded without failing other host operations

#### Scenario: Config backups tolerate the link
- **WHEN** an install, update, uninstall, or restore backs up or restores `config/`
- **THEN** the link is neither followed nor archived, and a restore keeps an existing link

#### Scenario: Restoration removes only the installer's link
- **WHEN** accepted uninstall restoration or transaction recovery runs
- **THEN** the link is removed only while it still points at the database directory; an operator-replaced entry is preserved

### Requirement: Safe unattended updates
Automatic updates SHALL require durable operator enrollment, use the same admission, ownership, recovery, activation, and persisted host-policy rules as direct installation, and advance release state only after successful activation.

#### Scenario: Enrolled release installation is idle and integrity checked
- **WHEN** an enrolled updater observes a new release checksum or missing or drifted optimized installation state
- **THEN** update proceeds only while the printer is idle and after archive integrity and path safety are verified
- **AND** missing or drifted state runs the current release installer even when its checksum is unchanged
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

### Requirement: THR firmware programming requires per-run opt-in
The installer SHALL ask supported interactive installations whether to flash the THR FIFO fix after preflight and before configuration changes, defaulting to No. An explicit yes or install-only CLI option SHALL authorize only that invocation. `--yes` alone, unattended updates, restore, and uninstall MUST NOT program MCU firmware or persist permission to do so.

#### Scenario: Firmware option is absent
- **WHEN** the operator declines, submits an empty answer, reaches end of input, or runs unattended without the explicit firmware option
- **THEN** no THR serial session, firmware backup, reset, or programming occurs

#### Scenario: Firmware option is explicitly selected
- **WHEN** an operator explicitly accepts the interactive question or selects the install-only THR firmware option
- **THEN** the installer explains the firmware/recovery risk and performs the operation under the installer lock after configuration installation and required activation
- **AND** the interactive question and README warn that input shaper calibration must be rerun after flashing; the installer does not initiate calibration
- **AND** after a verified transfer, and before Klipper restarts, the saved `SAVE_CONFIG` input shaper values are cleared while an empty `[input_shaper]` section remains, with the prior `printer.cfg` retained in the recovery files; an already-patched board keeps its calibration
- **AND** dry-run reports the proposed firmware work without service changes, serial access, or firmware backup creation

### Requirement: Optional THR transfer is admitted and byte-verified
The optional operation SHALL require supported firmware, idle ready state, zero heater targets, exclusive service ownership, and exact known THR application/bootloader identities. It MUST preserve stock recovery files before erase and verify the complete resulting application and unchanged bootloader before success.

#### Scenario: Known stock or patched application is detected
- **WHEN** safe preconditions hold and readback matches an admitted image
- **THEN** stock firmware receives only the pinned THR patch with retained recovery files
- **AND** an already-patched board is verified without another erase or transfer
- **AND** only previously active services are restored and printer readiness is checked

#### Scenario: Klipper is still restarting
- **WHEN** the operation starts while Klipper is restarting or Moonraker cannot yet report its state
- **THEN** the installer waits for Klipper to become ready before admission, allowing at least 60 seconds
- **AND** an active or paused print or a nonzero heater target fails admission without waiting
- **AND** if Klipper does not become ready in time, no service is stopped and no THR serial session or programming occurs

#### Scenario: Installed bootloader is unrecognized
- **WHEN** readback finds a THR bootloader that matches no admitted identity
- **THEN** the installer reports that the FIFO fix is unavailable for this bootloader and THR firmware was not changed
- **AND** it asks the operator to attach the capture's shareable summary to a GitHub issue
- **AND** the read-only capture stays with the recovery files, only previously active services are restored, and no firmware blocker remains
- **AND** the configuration installation result is unaffected

#### Scenario: Interrupted transfer falls back to stock firmware
- **WHEN** a recovery-mode transfer reports that the stock fallback image was programmed
- **THEN** the installer verifies complete readback against the stock application, restores previous service states without a firmware blocker, keeps input shaper calibration, and reports that the FIFO fix was not applied

#### Scenario: Admission fails or firmware work is interrupted
- **WHEN** firmware admission fails or firmware work does not reach verified readback
- **THEN** no unknown image is programmed and verified configuration installation is preserved
- **AND** potentially changed or unverified firmware retains recovery evidence, stopped serial-owning services, and a durable blocker against later installer operations
- **AND** configuration restore and uninstall never claim to revert MCU firmware

### Requirement: Package-owned Klipper extra modules
Install and update SHALL place each bundled package-owned Klipper extra module, together with the optimized configuration section that loads it, and uninstall SHALL remove the module only when it still matches the bundled payload.

#### Scenario: Install places and verifies the module
- **WHEN** install or update runs
- **THEN** each bundled extra module is written atomically to its `klippy/extras/tltg_*.py` destination and verified against the bundled payload
- **AND** an identical installed module is left unchanged

#### Scenario: Uninstall respects modified modules
- **WHEN** uninstall runs
- **THEN** an installed extra module that matches the bundled payload is removed along with the optimized configuration that loads it
- **AND** a modified module is left in place

### Requirement: QIDI Box motion settings in Fluidd
Normal install and update SHALL extend the recognized QIDI Fluidd bundle's Box Config view with a load and unload motion section that shows the feed-motion status and edits settings only through `TLTG_BOX_MOTION`, with the same recognition, preservation, service-worker revision, and restoration as the other Fluidd Box patches.

#### Scenario: Motion settings are shown per slot
- **WHEN** the feed-motion printer object is active
- **THEN** the Box Config view shows the global settings with vendor values for unset fields, and each slot's effective load and unload profile, its overrides, and the reason when a profile falls back to vendor motion

#### Scenario: Motion settings are edited through the command
- **WHEN** an operator applies global or slot settings, or resets them from the section
- **THEN** Fluidd sends the matching `TLTG_BOX_MOTION` command
- **AND** a refused command's reason is shown in the section

#### Scenario: Editing is unavailable while busy or inactive
- **WHEN** a print is running or paused, or the feed-motion object is absent or inactive
- **THEN** the section offers no editing controls, and an absent or inactive object shows its status instead of a profile

### Requirement: QIDI Box motion release defaults
The installer SHALL save the release Box motion profile only when no Box motion setting exists in Klipper saved variables.

#### Scenario: Printers without motion settings receive the release profile
- **WHEN** install, update, or idle automatic-update repair finds none of the Box motion settings
- **THEN** it saves the release profile through Moonraker after Klipper is ready and verifies the live values

#### Scenario: Operator motion settings are preserved
- **WHEN** any Box motion setting exists, including one saved as `None` to use the vendor value
- **THEN** no motion setting is written
- **AND** uninstall does not remove or reset the settings
