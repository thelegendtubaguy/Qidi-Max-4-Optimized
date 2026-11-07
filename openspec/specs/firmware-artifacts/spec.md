# firmware-artifacts Specification

## Purpose
Generate narrowly patched Max 4 firmware artifacts while preserving vendor components outside the approved fix.

## Requirements

### Requirement: Firmware generation is bound to a known release
The generator SHALL accept only the supported vendor archive and THR image, preserve the input, reject existing output destinations, and emit separately identified artifacts with checksums and provenance. Unknown, modified, or already-patched inputs MUST fail without producing a firmware package.

#### Scenario: Known release produces traceable artifacts
- **WHEN** the operator supplies the recognized vendor archive and a new output destination
- **THEN** generation produces a patched firmware ZIP, standalone THR image, checksums, and a provenance report identifying the input and output hashes
- **AND** the original archive remains unchanged

#### Scenario: Unsafe input or destination is rejected
- **WHEN** the input is unrecognized, modified, already patched, or the destination already exists
- **THEN** generation fails without overwriting existing data or emitting a firmware package

### Requirement: THR changes are limited to the FIFO correction
The generated THR SHALL immediately request another task when the LIS2DW FIFO contains samples and rearm polling when it is empty, preserving scheduler wake semantics. The package MUST preserve every other component payload, the firmware manifest, internal filenames, and vendor version identities. Generation MUST NOT flash hardware or invoke the macro installer.

#### Scenario: FIFO handling changes without replacing vendor components
- **WHEN** a recognized package is patched and verified
- **THEN** the THR differs only at the approved instruction edits and handles empty and nonempty FIFO states correctly
- **AND** sample reporting and overflow accounting remain intact
- **AND** all other archive members and the THR protocol dictionary are byte-identical to the input

### Requirement: Box changes are limited to the shutdown fix
The Box image SHALL be generated only from the pinned stock `02.03.01.21` application and SHALL differ from it only in skipping QIDI's faulty Box feeder shutdown block, the data dictionary's version string `02.03.01.21-tltg-shutdownfix1`, and the `identify` length constants for that dictionary. The bundle MUST NOT contain a QIDI Box image; the installer generates the patched image on the printer from the Box's own readback.

#### Scenario: Patched Box handles a shutdown
- **WHEN** a Box running the patched image shuts down
- **THEN** it completes its shutdown handlers and reports the original shutdown reason instead of re-entering shutdown
- **AND** the data dictionary it serves is identical to stock apart from the version

### Requirement: Mainboard changes are limited to the closed-loop reply fix
The Max 4 mainboard image SHALL be generated only from the pinned stock `02.01.01.12` application and SHALL differ from it only in its closed-loop reply-length lookup, the dictionary version `02.01.01.12-tltg-clreplies1` with matching `identify` lengths, and the lookup placed in the space the recompressed dictionary frees. The lookup MUST list only function codes whose driver replies have one fixed length. The bundle MUST NOT contain a QIDI mainboard image.

#### Scenario: Listed replies reach the host on their last byte
- **WHEN** a closed-loop driver reply with a listed function code arrives at a mainboard running the patched image
- **THEN** the mainboard forwards it to the host as soon as its last byte is parsed, instead of after 50 ms of bus silence
- **AND** the data dictionary it serves is identical to stock apart from the version

#### Scenario: Patched image comes from the board's own readback
- **WHEN** the mainboard fix is installed
- **THEN** the patched image is generated on the printer from the mainboard's verified stock readback

#### Scenario: Other replies are unchanged
- **WHEN** a reply with any other function code, malformed bytes, or noise arrives
- **THEN** the patched mainboard forwards exactly what stock forwards, at the same time
