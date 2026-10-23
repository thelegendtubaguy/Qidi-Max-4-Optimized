# thr-firmware-transfer Specification

## Purpose
Provide an explicitly operated Max 4 THR-only transfer path with known-image admission, recoverable artifacts, and byte-based installation evidence.

## Requirements

### Requirement: UART operations require explicit safe ownership
The tool SHALL refuse serial access unless the operator confirms the printer is idle and the serial-owning services and update timer are stopped. It MUST NOT modify printer configuration, control heaters or motion, or flash other boards.

#### Scenario: Serial ownership is unsafe
- **WHEN** idle confirmation is absent or a required service is not stopped
- **THEN** the tool fails before opening the UART

### Requirement: Erasing transfers require known images and recovery artifacts
The tool SHALL accept only supported stock or patched THR images and a bootloader identity whose transfer behavior has been validated. An erasing transfer MUST require explicit write confirmation and validated application/bootloader backups, and MUST use the transfer behavior validated for the bootloader identified by readback. Unknown inputs MUST fail before serial access.

#### Scenario: Confirmed known-image transfer
- **WHEN** an operator supplies a supported image, valid backups, explicit write confirmation, and readback identifies an admitted bootloader that returns its expected reply
- **THEN** the tool transfers only the THR application through bounded, acknowledgement-checked packets using that bootloader's validated behavior

#### Scenario: Unsafe transfer input
- **WHEN** an image, backup, confirmation, or bootloader identity is invalid
- **THEN** the tool issues no erase command

### Requirement: Probes do not erase and installation evidence uses readback
The tool SHALL distinguish non-erasing probes, completed transfers, and verified installations. A verified installation MUST match complete application readback and preserve the bootloader hash. Failed or incomplete transfers MUST report failure without claiming installation success.

#### Scenario: Non-erasing probe
- **WHEN** the operator probes an admitted bootloader
- **THEN** no application-start, data-programming, or erase command is sent

#### Scenario: Installation readback differs
- **WHEN** application readback differs from the selected image or bootloader readback changes
- **THEN** verification fails regardless of the vendor version string or transfer acknowledgements

### Requirement: Transfer recovery is limited to validated bootloader timing
For a bootloader whose session, exit, and startup timing has been validated, a transfer MAY run in recovery mode with the backup's stock application as the fallback. Recovery mode MUST be refused before serial access for any other bootloader. The outcome SHALL distinguish the requested image, the fallback image, data acknowledged without an end acknowledgement, and failure; none of them is installation evidence.

#### Scenario: Recovery mode on an unvalidated bootloader
- **WHEN** recovery mode is requested and the backup's bootloader has no validated timing
- **THEN** the tool fails before opening the UART

### Requirement: Transfer recovery never programs into an uncertain session
In recovery mode the tool SHALL resume the requested image when the failed exchange is idempotent, and SHALL otherwise let the bootloader's session expire and program the fallback in a new session. It MUST NOT send start into a session that may already hold programmed data, MUST NOT repeat an unacknowledged first data packet, and while the session state is uncertain MUST send only identity requests and idempotent data packets.

#### Scenario: Later data packet is interrupted
- **WHEN** a data packet after the first goes unacknowledged and the bootloader answers again within its session
- **THEN** the tool resumes from that packet and reports the requested image

#### Scenario: First data packet is ambiguous
- **WHEN** the first data packet is unacknowledged
- **THEN** the tool sends only identity requests until a new session is confirmed, then programs the fallback image

#### Scenario: New session is not confirmed
- **WHEN** repeated waits for any session to end never confirm a new session
- **THEN** the tool sends no start command and reports failure with the THR state unknown

### Requirement: Unrecognized bootloaders are captured without reset
When readback finds an unrecognized bootloader, the tool SHALL retain a private read-only capture of the bootloader and application region and MUST NOT reset, erase, or program the THR. The capture MUST NOT include the MCU unique device identifier, and SHALL include a shareable summary that contains no flash binaries.

#### Scenario: Unrecognized bootloader readback
- **WHEN** application readback succeeds and the bootloader matches no admitted identity
- **THEN** the capture is retained, no reset, erase, or programming command is sent, and the operation reports the bootloader as unsupported
