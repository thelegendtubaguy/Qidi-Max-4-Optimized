## ADDED Requirements

### Requirement: QIDI Plus 5 support
The installer SHALL admit QIDI Plus 5 firmware `01.01.02.01` as the Plus 5, with its own stock snapshot, guarded-patch variants, source-patch expectations, and macro folder. It SHALL apply Max 4 firmware and host fixes to a Plus 5 only where that Plus 5's hardware, bootloader, or kernel is recognized for them.

#### Scenario: Plus 5 firmware selects the Plus 5 baseline
- **WHEN** installation starts on firmware `01.01.02.01` whose firmware manifest SOC file starts with `QD_PLUS5_SOC_`
- **THEN** the Plus 5 stock snapshot, the Plus 5 variant of every guarded patch, and `installer/klipper/printers/plus5/` are used
- **AND** a guarded patch with no Plus 5 variant leaves the Plus 5's value unchanged

#### Scenario: Earlier Plus 5 firmware is refused
- **WHEN** installation starts on Plus 5 firmware `01.01.01.06` or `01.01.01.07`
- **THEN** the firmware is treated as unsupported and the operator is told to update to a supported release first

#### Scenario: Max 4 hardware fixes are not applied to the Plus 5
- **WHEN** install, update, or a firmware tool runs on a Plus 5
- **THEN** the mainboard closed-loop fix is not offered
- **AND** the THR and Box firmware fixes are offered only for bootloader builds already admitted for them
- **AND** zram modules load only on a kernel build declared for them

#### Scenario: The rotated Plus 5 screen is shown upright
- **WHEN** the Printer screen card shows a Plus 5, whose landscape UI is drawn into a 480×800 framebuffer
- **THEN** the card shows the UI upright
- **AND** a tap on the card presses the touchscreen at the control shown under it
