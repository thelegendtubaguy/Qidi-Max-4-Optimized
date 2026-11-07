# box-firmware-transfer Specification

## Purpose
Provide an explicitly operated transfer path for the USB QIDI Box and the Max 4 mainboard, both Klipper boards behind QIDI's USB bootloader, with known-image and bootloader-build admission, recoverable artifacts, and byte-based installation evidence.

## Requirements

### Requirement: Board serial operations require explicit safe ownership
The Box and mainboard transfer tools SHALL refuse serial access unless the operator confirms the printer is idle and Klipper, the touchscreen client, and the automatic-update timer are stopped. They MUST NOT modify printer configuration, control heaters or motion, or flash any board other than the addressed USB Box or the mainboard. Only `box-firmware.sh` and `mainboard-firmware.sh` reach them; install, update, automatic updates, and `--yes` never do.

#### Scenario: Serial ownership is unsafe
- **WHEN** idle confirmation is absent or a required service is still running
- **THEN** the tool fails before opening the board's serial port

### Requirement: Transfers admit only known images and bootloaders
The tools SHALL program only the pinned stock or patched application for that board, and only through a bootloader whose exact build has been validated, using backups of that board's bootloader and application. The mainboard fix is offered only on the Max 4. An erasing transfer MUST require explicit write confirmation. It MUST NOT resend the start command or an unacknowledged first data packet, because the bootloader's write position only rewinds at reset.

#### Scenario: Known image through an admitted bootloader
- **WHEN** the image, backups, and write confirmation are valid and the installed bootloader matches its backup
- **THEN** the tool resets the board into its bootloader and transfers the image in acknowledged 1 KiB packets

#### Scenario: Unknown input
- **WHEN** the image, backup, confirmation, or bootloader identity is not admitted
- **THEN** no reset or erase command is sent

### Requirement: Installation evidence uses readback
A Box or mainboard flash SHALL be reported as installed only when a full application readback matches the selected image and the bootloader readback matches the pre-transfer backup. Transfer acknowledgements and the reported version string are not installation evidence.

#### Scenario: Readback differs
- **WHEN** the application readback differs from the image or the bootloader changed
- **THEN** verification fails regardless of acknowledgements or version

### Requirement: Unrecognized builds are captured without reset
When readback finds a Box or mainboard bootloader or application that is not admitted, the tool SHALL keep a private read-only capture and a shareable summary without flash binaries or MCU unique identifiers, and MUST NOT reset, erase, or program that board.

#### Scenario: Unrecognized bootloader
- **WHEN** a board's bootloader matches no admitted build
- **THEN** that board is reported as not changed with the summary's location, and no reset, erase, or programming command is sent to it

### Requirement: Unverified flashes block until rescue
When programming may have begun and readback has not verified the board, the flow SHALL leave Klipper and the touchscreen stopped and keep a pending record that blocks every installer operation except that board's rescue. Rescue SHALL program QIDI's stock application from a verified backup or the printer's update folder through the waiting bootloader and verify it by readback before restoring services and clearing the record.

#### Scenario: Interrupted mainboard transfer
- **WHEN** a mainboard transfer fails after the application was erased
- **THEN** installs, updates, and Box operations refuse to run until `mainboard-firmware.sh rescue` restores and verifies stock firmware
