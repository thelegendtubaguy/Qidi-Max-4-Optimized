{if timelapse_type == 1} ; timelapse with wipe tower
G92 E0
G1 E-[retraction_length] F1800
G2 Z{layer_z + 0.4} I0.86 J0.86 P1 F20000 ; spiral lift a little
MOVE_TO_TRASH
{if layer_z <=25}
G1 Z25
{endif}
G92 E0
M400
TIMELAPSE_TAKE_FRAME
G1 E[retraction_length] F300
G1 X180 F8000
G1 Y380
{if layer_z <=25}
G1 Z[layer_z]
{endif}
{elsif timelapse_type == 0} ; timelapse without wipe tower
TIMELAPSE_TAKE_FRAME
{endif}
G92 E0
SET_PRINT_STATS_INFO CURRENT_LAYER={layer_num + 1}
