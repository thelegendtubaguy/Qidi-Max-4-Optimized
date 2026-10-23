# Spec Delta

## MODIFIED Requirements

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

#### Scenario: Admission fails or firmware work is interrupted
- **WHEN** firmware admission fails or firmware work does not reach verified readback
- **THEN** no unknown image is programmed and verified configuration installation is preserved
- **AND** potentially changed or unverified firmware retains recovery evidence, stopped serial-owning services, and a durable blocker against later installer operations
- **AND** configuration restore and uninstall never claim to revert MCU firmware
