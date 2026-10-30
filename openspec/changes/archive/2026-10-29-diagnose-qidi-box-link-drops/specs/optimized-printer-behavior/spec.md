## ADDED Requirements

### Requirement: QIDI Box processor temperature
Optimized configuration SHALL provide a temperature sensor named `BoxN_MCU` for the processor of each USB QIDI Box Klipper is configured with, numbered as that Box's MCU, and none when no Box is configured. These sensors SHALL set no temperature limits.

#### Scenario: One sensor per configured Box
- **WHEN** Klipper starts with zero to four USB Boxes configured
- **THEN** Fluidd's temperature card and graph show one `BoxN_MCU` sensor for each of them and no others

#### Scenario: A Box processor temperature never stops a print
- **WHEN** a Box processor temperature reads unusually high or low
- **THEN** the reading is reported and no shutdown or print error results from it

### Requirement: Optional QIDI Box link monitor evidence
The optional QIDI Box link monitor SHALL stay inert until its saved variable enables it. While enabled, it SHALL record each Box's reset reason labeled with the Box that reported it, link counters and print, heater, and Box processor temperature context for up to four Boxes, and, at the first link-failure line in `klippy.log`, each Box's recent sent and received messages with their times together with the kernel USB lines.

#### Scenario: Reset reasons name the reporting Box
- **WHEN** the monitor is enabled on a printer with two or more Boxes and Klipper connects
- **THEN** each Box's reset reason is recorded under that Box's name

#### Scenario: A link failure records what preceded it
- **WHEN** the monitor is enabled and `klippy.log` reports `Got EOF when reading from device`, `Timeout with MCU`, or `shutdown:`
- **THEN** the monitor log gains, once per Klipper connection, each Box's recent message history with host times, a clock reference for aligning them with kernel times, and the recent kernel USB lines

#### Scenario: Disabled monitor records nothing
- **WHEN** the monitor's saved variable is absent or false
- **THEN** no monitor log is written and printing is unaffected

### Requirement: Print-start mesh save does not block Klipper
When optimized print start calibrates a fresh adaptive mesh, it SHALL save the pending configuration to `printer.cfg` for power-loss recovery without blocking Klipper's main thread for the read, parse, and write. The saved file SHALL match what QIDI's `SAVE_CONFIG_QD` writes for the same pending values, `printer.cfg` SHALL exist at every moment of the save, and `SAVE_CONFIG` or `SAVE_CONFIG_QD` issued during the save SHALL wait for it to finish.

#### Scenario: Fresh mesh saved in the background
- **WHEN** optimized print start calibrates a fresh `kamp` mesh
- **THEN** the mesh and `profile_name` are saved for power-loss recovery
- **AND** print start continues while the file is written, with no Klipper stall from the save

#### Scenario: Background save fails
- **WHEN** the background save cannot write `printer.cfg` or a pending value conflicts with an included file
- **THEN** `printer.cfg` is left unchanged and the console reports the failure
- **AND** the print continues

#### Scenario: Config save during a background save
- **WHEN** `SAVE_CONFIG` or `SAVE_CONFIG_QD` runs while a background save is writing
- **THEN** it starts only after the background save finishes

### Requirement: QIDI Box heater refresh
Optimized configuration SHALL make each USB QIDI Box heater resend an unchanged output at most about one second after the last one it sent, so that a Klipper main-loop stall of up to about three seconds does not let the Box MCU's 5 s heater limit expire. Other heaters, heater limits, and heater verification SHALL be unchanged.

#### Scenario: Steady Box heater through a host stall
- **WHEN** a Box heater holds a steady output, including full power, and Klipper's main loop stalls for up to about three seconds
- **THEN** the Box heater output is refreshed before its MCU limit expires and the Box stays connected

#### Scenario: Other heaters keep Klipper's timing
- **WHEN** the extruder, bed, or chamber heater holds a steady output
- **THEN** it is resent on Klipper's normal schedule

### Requirement: Box heater sensors stop polling after a shutdown
Once Klipper has shut down, a failed read of a Box heater's AHT20 SHALL stop that sensor's polling instead of raising, so Klipper stays in its shutdown state with the original reason. While Klipper is not shut down, sensor read errors SHALL propagate unchanged.

#### Scenario: Box stays connected through a shutdown
- **WHEN** Klipper shuts down while a Box running the shutdown-fix firmware stays connected and refuses sensor reads
- **THEN** Klipper remains in its shutdown state showing the original reason and does not restart itself

