## ADDED Requirements

### Requirement: Package-built Fluidd
Normal install and update SHALL serve the package's pinned build of the project's Fluidd fork from a package-owned directory in place of QIDI's bundled Fluidd, independently of optional OS optimization policy, leaving QIDI's bundled Fluidd in place as the rollback. Fluidd requirements in this specification apply to whichever Fluidd nginx serves; their bundle patches apply only while QIDI's bundled Fluidd is served.

#### Scenario: The build is served instead of QIDI's bundle
- **WHEN** install or update runs with the build in the package and a recognized Fluidd nginx site
- **THEN** the build is extracted beside QIDI's bundle, readable by nginx, verified against the pinned checksum, and marked as package-owned
- **AND** only then is the nginx site switched to serve it, in the same guarded change that adds the printer-screen route
- **AND** QIDI's bundled Fluidd files are not modified

#### Scenario: Serving the build retires the bundle patches
- **WHEN** nginx serves the verified build
- **THEN** QIDI's bundle and service worker are not patched
- **AND** a bundle file patched by an earlier package version is restored from its retained preimage when it still matches that patch, and its ownership is released either way

#### Scenario: Updates replace the build as a unit
- **WHEN** the installed package build differs from the pinned build
- **THEN** the new build is staged completely before a single rename replaces the installed one, so nginx never serves a partial build
- **AND** a failure later in the same host transaction, or recovery of an interrupted one, puts the replaced build back; a completed transaction discards it

#### Scenario: QIDI's Fluidd stays in use when the build cannot be served
- **WHEN** the package has no build, the build directory exists without the package marker, or the nginx site is unrecognized or operator-modified
- **THEN** the existing directory and nginx site are left unchanged and the outcome is recorded without failing other host operations
- **AND** QIDI's bundle keeps receiving the Fluidd bundle patches

#### Scenario: Restoration returns to QIDI's Fluidd
- **WHEN** accepted uninstall restoration runs
- **THEN** the unchanged nginx site is restored before the build is removed
- **AND** the build is removed only while it carries the package marker and nginx no longer serves it; otherwise it is preserved and reported

## MODIFIED Requirements

### Requirement: Recoverable Fluidd QIDI Box filament display
Fluidd SHALL display and edit QIDI Box slots the way QIDI firmware `01.01.07.01` stores and resolves them, independently of optional OS optimization policy. While QIDI's bundled Fluidd is served, normal install and update SHALL provide this by patching the recognized bundle, retaining the original bundle and preserving unrecognized or operator-modified bundles.

#### Scenario: Box slots show the firmware's resolved filament
- **WHEN** Fluidd is connected to firmware that exposes `box485` and `multi_color_controller` slot information
- **THEN** each Box slot shows the filament name, vendor, and color the firmware resolved for that slot, including for saved IDs such as `QFA90`, RGB colors such as `["228332"]`, and stale numeric IDs
- **AND** an unknown filament ID displays as its ID

#### Scenario: Box pickers save firmware filament IDs and RGB colors
- **WHEN** an operator edits a slot in Fluidd on that firmware
- **THEN** the vendor picker lists the firmware filament database vendors and the filament picker lists the selected vendor's filaments
- **AND** choosing a filament saves its `QF` ID as a string, choosing a vendor saves that vendor's filament of the current type or its first filament, and choosing a color saves a one-element RGB list
- **AND** `vendor_slotN` is not written

#### Scenario: Box buttons use the firmware's Box commands
- **WHEN** Fluidd is connected to firmware that exposes `multi_color_controller`
- **THEN** the Eject, Load, Unload, and RFID controls send `EJECT_FILAMENT_CONTROL`, `LOAD_FILAMENT_CONTROL`, `UNLOAD_FILAMENT_CONTROL`, and `READ_RFID` with the selected slot number
- **AND** Load and Unload availability follows the Box path sensor from `box_extras` or, when `box_extras` omits it, from `multi_color_controller`

#### Scenario: Earlier firmware keeps stock pickers
- **WHEN** Fluidd is connected to firmware without `box485`
- **THEN** slots display through `officiall_filas_list.cfg` and the pickers save numeric IDs as QIDI's Fluidd did
- **AND** without `multi_color_controller`, the Box controls send the stock commands

#### Scenario: Browsers load the patched bundle
- **WHEN** a browser that previously cached Fluidd through its service worker opens Fluidd after the served Fluidd changes
- **THEN** the service worker updates and fetches the current Fluidd instead of serving the cached one
- **AND** while QIDI's bundle is served, the recognized service worker's bundle precache revision is set from the bundle patch, with the same recognition, preservation, and restoration as the bundle

#### Scenario: Unrecognized Fluidd bundles are preserved
- **WHEN** QIDI's bundle is served and the configured bundle is missing or does not match the reviewed stock source or an earlier package patch of it
- **THEN** the bundle is left unchanged and the outcome is recorded without failing other host patches

#### Scenario: Fluidd deployment remains reversible
- **WHEN** QIDI's bundle is served and the recognized bundle requires the patch
- **THEN** the installer backs up the original bytes and replaces the file atomically without restarting services
- **AND** a bundle carrying an earlier package patch is updated in place while the first restore preimage is retained
- **AND** accepted uninstall restoration reverts only the unchanged installed bundle; concurrent changes and operator drift are preserved

### Requirement: QIDI Box heater targets from Fluidd
Normal install and update SHALL patch recognized QIDI Klipper `box_config.py`, and Fluidd SHALL let its temperature panel set QIDI Box heater targets within the Box heater and loaded-filament limits, independently of optional OS optimization policy. While QIDI's bundled Fluidd is served, the recognized bundle is patched to provide the panel behavior. Original files are retained and unrecognized or operator-modified files are preserved.

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

### Requirement: Fluidd Box print slots can be shared
Fluidd's Box print dialog SHALL let several file filaments use the same Box slot, independently of optional OS optimization policy. While QIDI's bundled Fluidd is served, normal install and update SHALL provide this by patching the recognized bundle, with the same recognition, preservation, and restoration as the QIDI Box filament display patch.

#### Scenario: A slot is chosen for a second filament
- **WHEN** an operator starts a Box print from Fluidd and chooses a slot already chosen for another filament of the file
- **THEN** both filaments keep that slot, the other filament's choice is unchanged, and the print can start once every filament has a slot
- **AND** each filament's tool is mapped to its chosen slot when the print starts

### Requirement: Fluidd full display by default
Fluidd SHALL show the bed mesh card on the Tune page and temperature sensors without a target unless the operator turned them off in QIDI's Fluidd, independently of optional OS optimization policy. While QIDI's bundled Fluidd is served, normal install and update SHALL patch the recognized bundle so QIDI's "Enable Full Display" setting defaults on, with the same recognition, preservation, and restoration as the QIDI Box filament display patch.

#### Scenario: The package build shows everything
- **WHEN** Fluidd is served from the package build
- **THEN** the bed mesh card is on the Tune page and sensors without a target are in the temperature panel and chart, with no setting to hide them

#### Scenario: Full display is on unless the operator turned it off
- **WHEN** QIDI's bundled Fluidd loads settings that do not include a saved "Enable Full Display" value
- **THEN** full display is enabled, showing the bed mesh card on the Tune page and target-less temperature sensors in the temperature panel and chart
- **AND** a value saved from Fluidd's settings, including off, still applies

### Requirement: QIDI Box motion settings in Fluidd
Fluidd's Box settings SHALL include a load and unload motion section that shows the feed-motion status and edits settings only through `TLTG_BOX_MOTION`. While QIDI's bundled Fluidd is served, normal install and update SHALL provide it by extending the recognized bundle's Box Config view, with the same recognition, preservation, service-worker revision, and restoration as the other Fluidd Box patches.

#### Scenario: Motion settings are shown per slot
- **WHEN** the feed-motion printer object is active
- **THEN** the Box settings show the global settings with vendor values for unset fields, and each slot's effective load and unload profile, its overrides, and the reason when a profile falls back to vendor motion

#### Scenario: Motion settings are edited through the command
- **WHEN** an operator applies global or slot settings, or resets them from the section
- **THEN** Fluidd sends the matching `TLTG_BOX_MOTION` command
- **AND** a refused command's reason is shown in the section

#### Scenario: Editing is unavailable while busy or inactive
- **WHEN** a print is running or paused, or the feed-motion object is absent or inactive
- **THEN** the section offers no editing controls, and an absent or inactive object shows its status instead of a profile

### Requirement: QidiBox card in Fluidd
Fluidd SHALL provide a dashboard card that shows every QIDI Box slot at once: the package build's QIDI Box card or, while QIDI's bundled Fluidd is served, a QidiBox card that normal install and update add beside the stock Box card in the recognized bundle, with the same recognition, preservation, service-worker revision, and restoration as the other Fluidd Box patches.

#### Scenario: Every slot is shown at once
- **WHEN** Fluidd is connected to a printer with a configured Box
- **THEN** the card shows every Box's slots and the external spool together, each with the filament and color Fluidd resolves for it, whether filament is at the slot inlet, the tools mapped to it, and which slot feeds the extruder
- **AND** each Box shows its humidity, temperature, and active heater target, and the card shows the tool-to-slot mapping

#### Scenario: The filament path follows the sensors
- **WHEN** the operator selects a slot
- **THEN** the card draws that slot's filament to the slot inlet, past the hub, or into the toolhead as the slot inlet, hub, and toolhead sensors report it
- **AND** the shared hub and toolhead sensors are shown as detecting filament only for the slot whose filament they detect: the hub for the loaded slot, or the last-loaded slot when none is loaded, and the toolhead for the loaded slot

#### Scenario: Slot controls match the Box card
- **WHEN** the operator selects a slot and uses Load, Unload, Eject, Read RFID, or edits its filament
- **THEN** the card sends the Box commands and saves the slot values required by the QIDI Box filament display requirement
- **AND** the controls are unavailable while printing, while the Box runs an operation, or while Klipper is not ready
- **AND** Box settings opens QIDI's Box detection and automatic-reload settings and the load and unload motion settings

#### Scenario: Auto-reload groups are shown
- **WHEN** automatic reload is on
- **THEN** loaded Box slots with the same color, filament, and vendor, the slots QIDI's firmware can reload from each other, carry the same group marker
- **AND** the selected slot lists the other slots it can reload from, or that it has none
- **AND** when automatic reload is off, no group markers are shown and the selected slot says automatic reload is off

#### Scenario: Tool mappings are edited while idle
- **WHEN** the printer is idle and the operator edits the tool mapping from the card
- **THEN** the card saves each changed tool's slot to `value_tN` in the format Fluidd's print dialog uses and leaves unchanged tools alone
- **AND** Default proposes the identity mapping for every active Box slot
- **AND** editing is unavailable while a print is running or paused, while the Box runs an operation, or while Klipper is not ready

#### Scenario: Printers without a Box hide the card
- **WHEN** no Box is configured
- **THEN** the card is hidden

### Requirement: Printer screen in Fluidd
Normal install and update SHALL provide a Fluidd dashboard card that shows the live touchscreen and can operate it, served by a package-owned screen service and a Fluidd nginx route, independently of optional OS optimization policy, with the same recognition, preservation, and restoration as the other guarded host patches. The package build provides the card; while QIDI's bundled Fluidd is served, the recognized bundle is patched to add it, with the same service-worker revision as the other Fluidd bundle patches.

#### Scenario: The card is idle until expanded
- **WHEN** Fluidd opens a dashboard that has not shown the card before
- **THEN** a collapsed Printer screen card is present, and the screen is neither captured nor transferred until the card is expanded in a visible tab

#### Scenario: The screen is shown view-only by default
- **WHEN** the operator expands the card
- **THEN** it shows the touchscreen, updating when the screen changes, and clicks or taps on it do not reach the printer
- **AND** collapsing the card, leaving the dashboard, or hiding the tab disconnects it

#### Scenario: Control requires confirmation
- **WHEN** the operator enables control and confirms
- **THEN** clicks, taps, and drags on the image press the touchscreen at the matching position until control is turned off or the card disconnects
- **AND** a press in progress is released when the connection ends

#### Scenario: Access follows Moonraker authorization
- **WHEN** a client requests the screen
- **THEN** it is served only if Moonraker authorizes that client, by trusted address or by a one-shot token from the client's Fluidd session
- **AND** the service listens only on the printer's loopback address and refuses connections from other web origins

#### Scenario: Unavailable screens are reported
- **WHEN** the screen service, its route, the framebuffer, the touchscreen device, or the image encoder is unavailable
- **THEN** the expanded card says the screen is unavailable and why, and Fluidd otherwise works normally

#### Scenario: Screen deployment remains reversible
- **WHEN** install or update applies the service, its unit, or the nginx route
- **THEN** absent package files are created and enabled, files from earlier package versions are replaced, and a recognized nginx site is backed up and patched once, together with the switch to the package build
- **AND** unrecognized or operator-modified files are preserved and recorded without failing other host patches
- **AND** accepted uninstall restoration stops and disables the service, removes unchanged package files, and restores the unchanged nginx site
