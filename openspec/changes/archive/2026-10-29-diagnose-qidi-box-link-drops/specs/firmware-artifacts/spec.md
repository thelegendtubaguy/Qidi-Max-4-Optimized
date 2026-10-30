## ADDED Requirements

### Requirement: Box changes are limited to the shutdown fix
The Box image SHALL be generated only from the pinned stock `02.03.01.21` application and SHALL differ from it only in skipping QIDI's faulty Box feeder shutdown block, the data dictionary's version string `02.03.01.21-tltg-shutdownfix1`, and the `identify` length constants for that dictionary. The bundle MUST NOT contain a QIDI Box image; the installer generates the patched image on the printer from the Box's own readback.

#### Scenario: Patched Box handles a shutdown
- **WHEN** a Box running the patched image shuts down
- **THEN** it completes its shutdown handlers and reports the original shutdown reason instead of re-entering shutdown
- **AND** the data dictionary it serves is identical to stock apart from the version
