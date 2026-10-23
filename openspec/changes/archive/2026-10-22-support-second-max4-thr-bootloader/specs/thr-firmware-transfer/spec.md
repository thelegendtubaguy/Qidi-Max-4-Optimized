# Spec Delta

## MODIFIED Requirements

### Requirement: Erasing transfers require known images and recovery artifacts
The tool SHALL accept only supported stock or patched THR images and a bootloader identity whose transfer behavior has been validated. An erasing transfer MUST require explicit write confirmation and validated application/bootloader backups, and MUST use the transfer behavior validated for the bootloader identified by readback. Unknown inputs MUST fail before serial access.

#### Scenario: Confirmed known-image transfer
- **WHEN** an operator supplies a supported image, valid backups, explicit write confirmation, and readback identifies an admitted bootloader that returns its expected reply
- **THEN** the tool transfers only the THR application through bounded, acknowledgement-checked packets using that bootloader's validated behavior

#### Scenario: Unsafe transfer input
- **WHEN** an image, backup, confirmation, or bootloader identity is invalid
- **THEN** the tool issues no erase command

## ADDED Requirements

### Requirement: Unrecognized bootloaders are captured without reset
When readback finds an unrecognized bootloader, the tool SHALL retain a private read-only capture of the bootloader and application region and MUST NOT reset, erase, or program the THR. The capture MUST NOT include the MCU unique device identifier, and SHALL include a shareable summary that contains no flash binaries.

#### Scenario: Unrecognized bootloader readback
- **WHEN** application readback succeeds and the bootloader matches no admitted identity
- **THEN** the capture is retained, no reset, erase, or programming command is sent, and the operation reports the bootloader as unsupported
