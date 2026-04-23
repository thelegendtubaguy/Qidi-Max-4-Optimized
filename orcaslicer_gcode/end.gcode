SET_PRINT_MAIN_STATUS MAIN_STATUS=print_end
DISABLE_BOX_HEATER
M141 S0
M140 S0
DISABLE_ALL_SENSOR
G0 Z{min(max_print_height, max_layer_z + 3)} F600
OPTIMIZED_END_PRINT_FILAMENT_PREP T=[current_extruder]
OPTIMIZED_MOVE_TO_TRASH
{if max_layer_z < max_print_height / 2}G1 Z{min(max_print_height, max_print_height / 2 + 10)} F600{else}G1 Z{min(max_print_height, max_layer_z + 3)} F600{endif}
M104 S0
; Turn off Polar Cooler
M106 P4 S0
OPTIMIZED_END_FAN_COOLDOWN S=120 T=180
PRINT_END
