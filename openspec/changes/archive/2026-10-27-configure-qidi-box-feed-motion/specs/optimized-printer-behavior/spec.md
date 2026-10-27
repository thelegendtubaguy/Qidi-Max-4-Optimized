## ADDED Requirements

### Requirement: Operator-configurable QIDI Box feed motion
Optimized configuration SHALL let operators set the QIDI Box load fast distance, fast stage speeds, approach speed, and acceleration, and the unload stage speeds and acceleration, through Klipper saved variables, globally and per slot. It SHALL keep vendor motion whenever settings are absent, invalid, or unsupported. The load pre-stage, hot phases, and vendor flow control SHALL remain vendor-owned.

#### Scenario: Absent settings keep vendor motion
- **WHEN** no feed-motion settings are saved
- **THEN** Box loads and unloads move exactly as the vendor firmware does

#### Scenario: A load pushes fast, then approaches the toolhead switch
- **WHEN** a valid feed-motion profile is saved
- **AND** a Box load runs, including a tool change during a print
- **THEN** the Box pushes the filament at the configured fast stage speeds for the effective fast distance, then at the configured approach speed until the toolhead filament switch trips
- **AND** the load can reach at least as far as the vendor load before giving up
- **AND** cutting, synced extruder motion, purge, wipe, retries, error reporting, RFID, feed assist, and status are unchanged

#### Scenario: An unload uses the configured speeds
- **WHEN** a valid feed-motion profile is saved
- **AND** a Box unload runs
- **THEN** the Box-only retract to the hub sensor uses the configured unload speeds and acceleration and the vendor distances

#### Scenario: The extruder retract before the Box unload is configurable
- **WHEN** an extruder retract length is saved
- **THEN** every slot's unload retracts the extruder by that length in its second extruder retract, at the vendor speed
- **AND** the first extruder retract is unchanged
- **AND** the length cannot be overridden per slot

#### Scenario: Slot overrides take precedence
- **WHEN** a setting is saved for one slot
- **THEN** that slot's loads or unloads use it in place of the global setting or vendor value
- **AND** other slots are unaffected
- **AND** clearing the override returns the slot to the global setting

#### Scenario: An invalid profile falls back as a whole
- **WHEN** a slot's saved settings and overrides, combined with vendor values for anything unset, include an out-of-range value or form a profile the vendor planner cannot run
- **THEN** that slot's whole load or unload profile uses vendor motion
- **AND** the operator is told which check failed

#### Scenario: The fast distance applies as set
- **WHEN** a fast distance within its bounds is saved
- **THEN** the next load's fast push covers that distance, including when it is longer than the vendor's

#### Scenario: Unexpected vendor calls keep vendor motion
- **WHEN** QIDI's Box code lacks the load and unload methods, or a call's arguments don't match the traced shape or plausible values
- **THEN** feed-motion settings are not applied and vendor motion is unchanged

### Requirement: Published QIDI Box feed motion
The feed-motion integration SHALL publish its effective per-slot motion as Klipper printer-object status.

#### Scenario: Effective motion is published
- **WHEN** a client queries the feed-motion printer object
- **THEN** it reports whether the integration is active, the global settings, their bounds, and for each slot its overrides, the load and unload profile its next operation would use, and why a profile falls back to vendor motion
