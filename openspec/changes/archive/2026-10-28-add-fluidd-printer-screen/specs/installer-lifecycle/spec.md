## ADDED Requirements

### Requirement: Printer screen in Fluidd
Normal install and update SHALL provide a Fluidd dashboard card that shows the live touchscreen and can operate it, served by a package-owned screen service and a Fluidd nginx route, independently of optional OS optimization policy, with the same recognition, preservation, service-worker revision, and restoration as the other guarded host patches.

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
- **THEN** absent package files are created and enabled, files from earlier package versions are replaced, and a recognized nginx site is backed up and patched once
- **AND** unrecognized or operator-modified files are preserved and recorded without failing other host patches
- **AND** accepted uninstall restoration stops and disables the service, removes unchanged package files, and restores the unchanged nginx site
