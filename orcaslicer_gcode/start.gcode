;===== PRINT_PHASE_INIT =====
SET_PRINT_STATS_INFO TOTAL_LAYER=[total_layer_count]
SET_PRINT_MAIN_STATUS MAIN_STATUS=print_start
M220 S100
M221 S100
SET_INPUT_SHAPER SHAPER_TYPE_X=mzv
SET_INPUT_SHAPER SHAPER_TYPE_Y=mzv
DISABLE_ALL_SENSOR
M1002 R1
M107
CLEAR_PAUSE
M140 S[bed_temperature_initial_layer_single]
M141 S[chamber_temperature]
G29.0
OPTIMIZED_PRINT_START_HOME

;===== BOX_PREPAR =====
OPTIMIZED_START_PRINT_FILAMENT_PREP EXTRUDER=[initial_no_support_extruder] FIRSTLAYERTEMP=[nozzle_temperature_initial_layer] PURGETEMP={nozzle_temperature_range_high[initial_tool]} BEDTEMP=[bed_temperature_initial_layer_single] CHAMBER=[chamber_temperature]

;===== PRINT_START =====
; Turn on Polar cooler, comment out if you don't want this
M106 P4 S255
; Set total layer count for progress reporting.
SET_PRINT_STATS_INFO TOTAL_LAYER=[total_layer_count]
; Select the initial tool before the front prime line.
T[initial_tool]
; Set bed target temperature (do not wait).
M140 S[bed_temperature_initial_layer_single]
; Set chamber target temperature (do not wait).
M141 S[chamber_temperature]
; Use absolute coordinates for the front purge line.
G90
; Move to the centered front purge lead-in point before the first-layer nozzle wait.
G1 Z5 F1200
G1 X210 Y0 F20000
; Wait for nozzle to be fully back at first-layer temperature over the lead-in zone.
M109 S[nozzle_temperature_initial_layer]
; Use relative extrusion for the purge line.
M83
; Reset extruder position before priming.
G92 E0
; Draw a fat front purge line to consume high-temp ooze from the final heat-up.
G1 Z0.5 F900
G1 X218 Y0 F12000
G1 Z{initial_layer_print_height} F1200
G1 E6 F300
M106 S200
G1 X178 E20 F1200
G1 F6000
G1 X173 E0.8
; Relieve pressure before the nozzle lifts and the startup setup block runs.
G1 E-0.2 F1800
; Lift off after the tapered finish and pressure relief.
G1 Z1 F1200
; Turn the part cooling fan back off after the purge.
M106 S0
; Reset extruder position for the print proper.
G92 E0
; Restore absolute extrusion mode for sliced moves.
M82
; Mark printer status as actively printing after startup completes.
SET_PRINT_MAIN_STATUS MAIN_STATUS=printing
