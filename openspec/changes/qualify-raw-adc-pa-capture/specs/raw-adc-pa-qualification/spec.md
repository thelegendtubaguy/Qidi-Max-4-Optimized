## ADDED Requirements

### Requirement: Experimental capture remains separate from production
The system SHALL keep production calibration and existing direct/origin capture gates disabled while raw acquisition is unqualified. A new characterization harness SHALL be independently source-gated and disabled by default. Creating qualification artifacts SHALL NOT authorize printer contact or physical testing.

#### Scenario: Packaged default remains inert
- **WHEN** an operator invokes an unqualified capture or calibration entrypoint in the default package
- **THEN** it rejects the request before sensor commands, heating, motion, extrusion, or PA mutation

### Requirement: Raw capture is bounded and non-zeroing
The characterization harness SHALL use nonblocking raw acquisition with one outstanding request, explicit request and duration limits, bounded retained records, and a response deadline. It SHALL NOT retransmit requests at the host layer, zero the sensor, configure it, arm homing, or start or stop periodic polling.

#### Scenario: Bounded capture succeeds
- **WHEN** exclusive host ownership and supported bindings are established and responses arrive within the configured bounds
- **THEN** capture retains raw payloads and host timing records without claiming conversion timestamps
- **AND** equal payloads or transport timestamps are preserved rather than deduplicated
- **AND** capture ends within its bounds and releases only its owned resources

#### Scenario: Capture cannot safely continue
- **WHEN** ownership conflicts, a deadline expires, record limits are exceeded, cancellation occurs, or the connection shuts down
- **THEN** capture stops issuing requests and reports an incomplete or failed result
- **AND** cleanup is idempotent and does not remove another owner's handler
- **AND** late responses cannot be attributed to a subsequent capture; capture remains blocked if safe separation is unproven

### Requirement: Qualification preserves probing state and exposes uncertainty
The harness SHALL use correctly mapped read-only homing-state and stored-reference observations before and after capture. It SHALL distinguish empty, malformed/sentinel, unexpected, and missing responses without claiming equal-valued replies are necessarily stale or fresh. It SHALL NOT report a successful qualification when post-state is changed or unverifiable.

#### Scenario: State preservation cannot be established
- **WHEN** homing is armed, the stored reference changes, or post-capture state cannot be verified
- **THEN** the run is invalidated and further experimentation is blocked pending explicit recovery
- **AND** cleanup does not attempt reference restoration by zeroing or ADC reconfiguration

### Requirement: Hardware qualification proceeds through explicit evidence gates
The qualification workflow SHALL require separate authorization and the mandatory printer-state guard before physical access. Initial hardware capture SHALL be idle and cold without movement or extrusion. Heated trials SHALL follow successful idle characterization and retain bounded extrusion, chute clearing, and state restoration. A PA recommendation SHALL require repeatable and reordered trials plus printed comparison, not response cadence alone.

#### Scenario: Evidence supports only acquisition characterization
- **WHEN** local emulation or cold-idle capture succeeds without loaded and printed validation
- **THEN** the result is recorded as acquisition evidence only
- **AND** production calibration remains disabled

#### Scenario: Practical PA discrimination is assessed
- **WHEN** authorized conditioned trials repeat and reorder candidate PA settings
- **THEN** the assessment includes drift, noise, payload anomalies, timing uncertainty, state restoration, and printed comparisons
- **AND** a useful repeatable value or range may be accepted without exact conversion timestamps only when that uncertainty does not dominate the recommendation
- **AND** inconclusive evidence produces no automatic PA application or production enablement
