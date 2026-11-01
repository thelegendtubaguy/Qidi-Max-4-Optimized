## ADDED Requirements

### Requirement: Box firmware runs only through its dedicated script
The installer bundle SHALL provide `box-firmware.sh` with `status`, `install`, `restore`, and `rescue` actions, and `status` SHALL be read-only. Install, update, uninstall, restore, and automatic updates MUST NOT flash Box firmware or offer to, and `--yes` MUST NOT authorize it.

#### Scenario: Normal installer runs
- **WHEN** the installer installs, updates, or runs an automatic update, with or without `--yes`
- **THEN** no Box serial session, reset, or programming occurs and no Box firmware question is asked

### Requirement: Box firmware operations are confirmed and restore services
`install` and `restore` SHALL default to every configured USB Box and accept `--box N` to limit them. They SHALL require an idle ready printer with every heater target at zero, show the plan, program only after the operator types `FLASH`, and restore previously active services afterwards.

#### Scenario: Operator flashes Boxes
- **WHEN** the operator runs `box-firmware.sh install`, confirms with `FLASH`, and the printer is idle with zero heater targets
- **THEN** each Box with stock firmware is backed up, flashed with the fix, and verified by readback, Boxes already fixed or not recognized are left unchanged, and previously active services are restored

#### Scenario: Unsafe state or no confirmation
- **WHEN** the printer is printing, a heater target is nonzero, or the operator types anything other than `FLASH`
- **THEN** no service is stopped and no Box is touched

#### Scenario: A Box flash fails
- **WHEN** a Box transfer or readback fails after programming may have started
- **THEN** Klipper and the touchscreen stay stopped, a pending Box firmware record blocks other installer operations, and the output names the `rescue` command
- **AND** `box-firmware.sh rescue --box N` flashes and verifies QIDI's stock Box firmware, restores the recorded services, and clears the record
