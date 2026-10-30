# box-firmware-transfer Specification

## Purpose
Provide an explicitly operated USB QIDI Box transfer path with known-image and bootloader-build admission, recoverable artifacts, and byte-based installation evidence.

## Requirements

### Requirement: Box serial operations require explicit safe ownership
The Box transfer tool SHALL refuse Box serial access unless the operator confirms the printer is idle and Klipper, the touchscreen client, and the automatic-update timer are stopped. It MUST NOT modify printer configuration, control heaters or motion, or flash any board other than the addressed USB Box.

#### Scenario: Serial ownership is unsafe
- **WHEN** idle confirmation is absent or a required service is still running
- **THEN** the tool fails before opening the Box's serial port

### Requirement: Box transfers admit only known images and bootloaders
The tool SHALL program only the pinned stock or patched Box application, and only through a bootloader whose exact build has been validated, using backups of that Box's bootloader and application. An erasing transfer MUST require explicit write confirmation. It MUST NOT resend the start command or an unacknowledged first data packet, because the bootloader's write position only rewinds at reset.

#### Scenario: Known image through an admitted bootloader
- **WHEN** the image, backups, and write confirmation are valid and the installed bootloader matches its backup
- **THEN** the tool resets the Box into its bootloader and transfers the image in acknowledged 1 KiB packets

#### Scenario: Unknown input
- **WHEN** the image, backup, confirmation, or bootloader identity is not admitted
- **THEN** no reset or erase command is sent

### Requirement: Box installation evidence uses readback
A Box flash SHALL be reported as installed only when a full application readback matches the selected image and the bootloader readback matches the pre-transfer backup. Transfer acknowledgements and the reported version string are not installation evidence.

#### Scenario: Readback differs
- **WHEN** the application readback differs from the image or the bootloader changed
- **THEN** verification fails regardless of acknowledgements or version

### Requirement: Unrecognized Box builds are captured without reset
When readback finds a Box bootloader or application that is not admitted, the tool SHALL keep a private read-only capture and a shareable summary without flash binaries or MCU unique identifiers, and MUST NOT reset, erase, or program that Box.

#### Scenario: Unrecognized bootloader
- **WHEN** a Box's bootloader matches no admitted build
- **THEN** that Box is reported as not changed with the summary's location, and no reset, erase, or programming command is sent to it
