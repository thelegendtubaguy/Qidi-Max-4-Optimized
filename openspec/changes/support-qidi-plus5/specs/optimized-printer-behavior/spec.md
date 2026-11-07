## ADDED Requirements

### Requirement: Plus 5 motion follows its own hardware
On the Plus 5, the optimized macros SHALL use the Plus 5's homing sequence, positions, cutter, wiper, and waste-chute coordinates under the same macro names as on the Max 4, and SHALL issue no QIDI closed-loop driver command.

#### Scenario: Plus 5 homing keeps QIDI's sensorless sequence
- **WHEN** X or Y homes on a Plus 5
- **THEN** both X/Y drivers use QIDI's homing current during the home, `run_current` is restored afterwards, and each axis backs off as QIDI's Plus 5 macros do
- **AND** no closed-loop homing mode or enforce-mode command is sent

#### Scenario: Plus 5 nozzle moves stay within its travel
- **WHEN** the optimized cut, wipe, chute, park, or print-start moves run on a Plus 5
- **THEN** they use the Plus 5's coordinates, all inside its configured X −7–326 and Y −5–340 travel

#### Scenario: Plus 5 speed limits stay at QIDI's values
- **WHEN** install or update runs on a Plus 5
- **THEN** `max_velocity`, Z tilt `speed`, and bed mesh `speed` keep the Plus 5's own values rather than the Max 4's 565 mm/s cap

#### Scenario: Plus 5 slicer start uses its own prime line
- **WHEN** a print sliced with the project's Plus 5 OrcaSlicer or QIDI Studio pack starts
- **THEN** its start path follows the Plus 5 start-print contract, including the Plus 5 prime line and `M1006 Z` temperature compensation
