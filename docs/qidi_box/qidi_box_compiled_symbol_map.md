# QIDI Box compiled symbol map

## Source

Static disassembly triage: `docs/qidi_box/qidi_box_static_disassembly_notes.md`.

Symbol dumps generated with local `objdump -t` from captured aarch64 ELF extension modules:

- `tmp/qidi-box-reversing/symbol-dumps/box_stepper.objdump-symbols.txt`
- `tmp/qidi-box-reversing/symbol-dumps/box_extras.objdump-symbols.txt`
- `tmp/qidi-box-reversing/symbol-dumps/box_autofeed.objdump-symbols.txt`
- `tmp/qidi-box-reversing/symbol-dumps/box_rfid.objdump-symbols.txt`
- `tmp/qidi-box-reversing/symbol-dumps/multi_color_controller.objdump-symbols.txt`
- `tmp/qidi-box-reversing/symbol-dumps/box_detect.objdump-symbols.txt`

Cython function symbols are present as local `.text` symbols. Symbol size gives a useful priority order for deeper disassembly.

## `box_stepper.so` priority functions

| Size | Address | Symbol |
|---:|---|---|
| `0xca90` | `0x400d8` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_42cmd_EXTRUDER_UNLOAD` |
| `0x7aa4` | `0x19368` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_16do_move_triple_steps` |
| `0x7738` | `0x38568` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_40cmd_EXTRUDER_LOAD` |
| `0x4d8c` | `0x13a10` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_14do_move_double_steps` |
| `0x3814` | `0x2df84` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_32do_home_three_steps` |
| `0x3608` | `0x2a2b4` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_30do_home_double_steps` |
| `0x3450` | `0x26870` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_28do_home` |
| `0x2f2c` | `0x32750` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_36slot_load` |
| `0x27d4` | `0x35a08` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_38cmd_SLOT_UNLOAD` |
| `0x252c` | `0x526ac` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_54switch_next_slot` |
| `0x2424` | `0x54f64` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_56cmd_SLOT_RFID_READ` |
| `0x22a0` | `0x4d898` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_46slot_sync` |
| `0x1d38` | `0x22738` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_24_calc_endstop_rate` |
| `0x1c60` | `0x57714` | `__pyx_pf_11box_stepper_18BoxExtruderStepper_58set_led` |

`cmd_EXTRUDER_LOAD` and `cmd_EXTRUDER_UNLOAD` are large enough to contain branch predicates in addition to recovered movement constants. `do_home`, `do_home_double_steps`, `do_home_three_steps`, `do_move_double_steps`, and `do_move_triple_steps` are the reusable motion primitives inside `box_stepper.so`.

## `box_extras.so` priority functions

| Size | Address | Symbol |
|---:|---|---|
| `0x4fc0` | `0x12a4c` | `__pyx_pf_10box_extras_9BoxExtras___init__` |
| `0x45bc` | `0x51a84` | `__pyx_pf_10box_extras_9BoxExtras_88cmd_TRY_RESUME_PRINT` |
| `0x3ef8` | `0x38cf8` | `__pyx_pf_10box_extras_9BoxExtras_50set_box_temp` |
| `0x3b34` | `0x599c0` | `__pyx_pf_10box_extras_9BoxExtras_92cmd_RESUME_PRINT_1` |
| `0x33e8` | `0x2f050` | `__pyx_pf_10box_extras_9BoxExtras_40button_extruder_load` |
| `0x3260` | `0x563d0` | `__pyx_pf_10box_extras_9BoxExtras_90cmd_BOX_PRINT_START` |
| `0x2a94` | `0x2c22c` | `__pyx_pf_10box_extras_9BoxExtras_38cmd_RETRY` |
| `0x1f9c` | `0x22120` | `__pyx_pf_10box_extras_9BoxExtras_16detect_filament_loaded` |
| `0x1f54` | `0x26c90` | `__pyx_pf_10box_extras_9BoxExtras_28cmd_RELOAD_ALL` |
| `0x1d78` | `0x329ac` | `__pyx_pf_10box_extras_9BoxExtras_42button_extruder_unload` |
| `0x16e0` | `0x2a7bc` | `__pyx_pf_10box_extras_9BoxExtras_36cmd_AUTO_RELOAD_FILAMENT` |
| `0xeac` | `0x366d0` | `__pyx_pf_10box_extras_9BoxExtras_46cmd_INIT_RFID_READ` |
| `0xb94` | `0x46030` | `__pyx_pf_10box_extras_9BoxExtras_66cmd_TIGHTEN_FILAMENT` |
| `0xa08` | `0x29a24` | `__pyx_pf_10box_extras_9BoxExtras_34cmd_CUT_FILAMENT` |
| `0x820` | `0x46f8c` | `__pyx_pf_10box_extras_9BoxExtras_68get_status` |
| `0x588` | `0x3f79c` | `__pyx_pf_10box_extras_9BoxExtras_56cmd_RUN_STEPPER` |
| `0x2bc` | `0x459e4` | `__pyx_pf_10box_extras_9BoxExtras_64cmd_CLEAR_RUNOUT_NUM` |

`BOX_PRINT_START`, button load/unload, retry, resume, and auto-reload are the high-value orchestration targets. Targeted disassembly artifacts for `cmd_BOX_PRINT_START`, `cmd_RETRY`, `cmd_TRY_RESUME_PRINT`, and `cmd_RESUME_PRINT_1` are listed in `docs/qidi_box/qidi_box_static_disassembly_notes.md`. `cmd_RUN_STEPPER`, `cmd_CLEAR_RUNOUT_NUM`, `cmd_CLEAR_FLUSH`, `cmd_CLEAR_OOZE`, and `cmd_CUT_FILAMENT` are small enough that harnessing or runtime log capture is likely more efficient than full disassembly.

## `box_autofeed.so` priority functions

| Size | Address | Symbol |
|---:|---|---|
| `0x3afc` | `0x21b6c` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_41cmd_auto_start` |
| `0x33d8` | `0x25b84` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_43auto_start` |
| `0x2794` | `0x86d4` | `__pyx_pf_12box_autofeed_parse_pin_desc` |
| `0x22bc` | `0xb1f4` | `__pyx_pf_12box_autofeed_11MCBAutoFeed___init__` |
| `0x1e20` | `0x1b8f8` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_29limit_a_event` |
| `0x1aac` | `0x2c490` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_57wrapping_operate` |
| `0x1870` | `0x153cc` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_17_build_config_for_dev` |
| `0x184c` | `0x17914` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_21_get_stepper_mcu_and_enable` |
| `0x1078` | `0x194ec` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_23_select_slot` |
| `0xef4` | `0x1daa4` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_31cmd_config` |
| `0x860` | `0x1ed24` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_33cmd_query` |
| `0x5cc` | `0x2e764` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_59wrapping_detection` |
| `0x3cc` | `0x1f910` | `__pyx_pf_12box_autofeed_11MCBAutoFeed_35cmd_SET_LIMIT_A` |

Targeted disassembly artifacts for `cmd_auto_start`, `auto_start`, `limit_a_event`, `wrapping_operate`, and `wrapping_detection` are listed in `docs/qidi_box/qidi_box_static_disassembly_notes.md`. `wrapping_detection` is comparatively small; its unknown behavior is mostly in the event callbacks and MCU response path rather than a large local state machine.

## `box_rfid.so` priority functions

| Size | Address | Symbol |
|---:|---|---|
| `0x2764` | `0x7e1c` | `__pyx_pf_8box_rfid_7BoxRFID_8_schedule_rfid_read` |
| `0x1ac0` | `0x4e78` | `__pyx_pf_8box_rfid_7BoxRFID___init__` |
| `0x7bc` | `0xa90c` | `__pyx_pf_8box_rfid_7BoxRFID_10start_rfid_read` |
| `0x6ec` | `0xb3ec` | `__pyx_pf_8box_rfid_7BoxRFID_12stop_read` |
| `0x410` | `0x6c5c` | `__pyx_pf_8box_rfid_7BoxRFID_2_build_config` |
| `0x2a4` | `0x7390` | `__pyx_pf_8box_rfid_7BoxRFID_4read_card` |
| `0x138` | `0x7958` | `__pyx_pf_8box_rfid_7BoxRFID_6read_card_from_slot` |

Targeted disassembly artifacts for `_schedule_rfid_read`, `start_rfid_read`, and `stop_read` are listed in `docs/qidi_box/qidi_box_static_disassembly_notes.md`. RFID complexity is concentrated in scheduling and retry behavior rather than in `read_card_from_slot`. Full metadata behavior still requires live tag data capture because strings and symbols do not reveal actual tag payload examples.

## `multi_color_controller.so` priority functions

| Size | Address | Symbol |
|---:|---|---|
| `0x49f0` | `0x91478` | `__pyx_pf_22multi_color_controller_20MultiColorController_20cmd_query_multi_color` |
| `0x416c` | `0x8cf78` | `__pyx_pf_22multi_color_controller_20MultiColorController_18_register_commands` |
| `0x3f20` | `0xf864` | `__pyx_pf_22multi_color_controller_16MaterialDatabase_2load_config` |
| `0x3cac` | `0x4fa80` | `__pyx_pf_22multi_color_controller_13RemoteAdapter_10_update_state_from_response` |
| `0x3794` | `0x2ce84` | `__pyx_pf_22multi_color_controller_12LocalAdapter_6update_state` |
| `0x34d8` | `0x961fc` | `__pyx_pf_22multi_color_controller_20MultiColorController_22cmd_multi_color_load` |
| `0x22a0` | `0x99a68` | `__pyx_pf_22multi_color_controller_20MultiColorController_24cmd_multi_color_unload` |
| `0x2478` | `0x89704` | `__pyx_pf_22multi_color_controller_20MultiColorController_12_sync_external_context` |
| `0x1f9c` | `0xba080` | `__pyx_pf_22multi_color_controller_20MultiColorController_72cmd_set_save_variable` |
| `0x1e50` | `0x15d54` | `__pyx_pf_22multi_color_controller_12UnifiedState_2to_dict` |
| `0x1c68` | `0xa19dc` | `__pyx_pf_22multi_color_controller_20MultiColorController_32cmd_multi_color_sync` |
| `0x1ac8` | `0xb8220` | `__pyx_pf_22multi_color_controller_20MultiColorController_70cmd_query_save_variables` |
| `0x179c` | `0xbc3b4` | `__pyx_pf_22multi_color_controller_20MultiColorController_74cmd_reset_save_variables` |
| `0x1614` | `0x556c8` | `__pyx_pf_22multi_color_controller_13RemoteAdapter_14unload_filament` |
| `0x15d8` | `0x33b50` | `__pyx_pf_22multi_color_controller_12LocalAdapter_12swap_filament` |
| `0x13a8` | `0xa7690` | `__pyx_pf_22multi_color_controller_20MultiColorController_38cmd_multi_color_box_unload` |
| `0x12e8` | `0x32104` | `__pyx_pf_22multi_color_controller_12LocalAdapter_10unload_filament` |
| `0x12a8` | `0x1c934` | `__pyx_pf_22multi_color_controller_16TaskQueueManager_12_check_step_finished` |
| `0x1210` | `0x1b390` | `__pyx_pf_22multi_color_controller_16TaskQueueManager_10_is_group_completed` |
| `0x11ac` | `0x443e4` | `__pyx_pf_22multi_color_controller_12LocalAdapter_48set_temp` |
| `0x10f4` | `0x5b7bc` | `__pyx_pf_22multi_color_controller_13RemoteAdapter_22read_rfid` |
| `0x10ec` | `0x9c09c` | `__pyx_pf_22multi_color_controller_20MultiColorController_26cmd_multi_color_swap` |
| `0x1058` | `0x689b0` | `__pyx_pf_22multi_color_controller_13RemoteAdapter_42print_start` |
| `0xcac` | `0x1ef3c` | `__pyx_pf_22multi_color_controller_16TaskQueueManager_16_decide_flow_id` |
| `0xb6c` | `0x1df04` | `__pyx_pf_22multi_color_controller_16TaskQueueManager_14_move_next` |
| `0x6f4` | `0x18b28` | `__pyx_pf_22multi_color_controller_16TaskQueueManager_4start_flow` |
| `0x4dc` | `0x19b58` | `__pyx_pf_22multi_color_controller_16TaskQueueManager_8tick` |

`TaskQueueManager._decide_flow_id` is only `0xcac` bytes; targeted disassembly or a more complete harness is realistic. `cmd_multi_color_load` and `cmd_multi_color_unload` are much larger because they validate command parameters, state, and dispatch into the task queue and adapter. `LocalAdapter.update_state` and `UnifiedState.to_dict` define the Moonraker status shape captured in `docs/qidi_box/qidi_box_runtime_observations.md`.

## `box_detect.so` priority functions

| Size | Address | Symbol |
|---:|---|---|
| `0xb418` | `0xa298` | `__pyx_pf_10box_detect_9BoxDetect_6monitor_serial_by_id` |
| `0x7b5c` | `0x1bbc0` | `__pyx_pf_10box_detect_monitor_serial_devices` |
| `0x2c28` | `0x24700` | `__pyx_pf_10box_detect_4update_monitor_config_file` |
| `0x1558` | `0x15af0` | `__pyx_pf_10box_detect_9BoxDetect_8_update_config_file` |
| `0x1064` | `0x8ea8` | `__pyx_pf_10box_detect_9BoxDetect_4get_config_mcu_serials` |
| `0x1060` | `0x71f0` | `__pyx_pf_10box_detect_9BoxDetect___init__` |
| `0xb40` | `0x18b5c` | `__pyx_pf_10box_detect_9BoxDetect_14count_box_includes` |
| `0xa58` | `0x17d78` | `__pyx_pf_10box_detect_9BoxDetect_12get_check_serials_id` |

`box_detect.so` owns dynamic serial monitoring and config-file mutation; it is not part of load/unload motion control.

## Disassembly target order

1. `box_stepper`: `cmd_EXTRUDER_LOAD`, `cmd_EXTRUDER_UNLOAD`, `cmd_SLOT_UNLOAD`, `slot_load`, `slot_sync`.
2. `multi_color_controller`: `TaskQueueManager._decide_flow_id`, `TaskQueueManager._move_next`, `TaskQueueManager._check_step_finished`, `cmd_multi_color_load`, `cmd_multi_color_unload`.
3. `box_autofeed`: `cmd_auto_start`, `auto_start`, `limit_a_event`, `wrapping_operate`, `wrapping_detection`.
4. `box_rfid`: `schedule_rfid_read`, `start_rfid_read`, `stop_read`.
5. `box_extras`: `cmd_BOX_PRINT_START`, `cmd_RETRY`, `cmd_TRY_RESUME_PRINT`, `cmd_RESUME_PRINT_1`, `button_extruder_load`, `button_extruder_unload`.
