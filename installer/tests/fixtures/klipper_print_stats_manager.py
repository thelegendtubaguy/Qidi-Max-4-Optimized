# QIDI Max 4 firmware 01.01.07.01 /home/qidi/klipper/klippy/extras/print_stats_manager.py (01.01.06.04 is identical).
# Klipper is distributed under GNU GPLv3. The live file uses CRLF line endings.
# klippy/extras/print_stats_manager.py
# Klipper Status Management Module
#
# Copyright (C) 2023 Your Name <your.email@example.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
from collections import deque

class PrintStatusManager:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        
        # Status tracking
        self.current_main_status = "ready"
        self.current_sub_status = ""
        self.current_step = 0
        self.main_status_stack = deque()
        self.sub_status_stack = deque()
        
        # Event handlers: key: status, value: list of handlers
        self.event_handlers = {}
        
        # Available statuses
        self.main_status_list = [
            'ready', 'filament_load', 'filament_unload', 'bed_heating',
            'chamber_heating', 'homing', 'leveling_gantry', 'calibrating_z',
            'meshing', 'extruder_heating', 'purging', 'printing', 'pausing',
            'cancelling', 'completing', 'clear_nozzle', 'leveling_calibration',
            'extruder_cooling', 'z_tilt_homing', 'input_shaping',
            'print_start','print_completing', 'filament_load_6', 'filament_unload_7',
            'print_end'
        ]

        self.sub_status_list = {"print_start":["tool_head_reset","change_filament","flush_filament","clear_nozzle",
                                               "wait_bed_temp","wait_chamber_temp","z_tilt_adjust","auto_bed_adjust"]}
        
        # Register GCode commands
        self.gcode.register_command('SET_PRINT_MAIN_STATUS',
                                   self.cmd_SET_PRINT_MAIN_STATUS,
                                   desc=self.cmd_SET_PRINT_MAIN_STATUS_help)
        self.gcode.register_command('SET_PRINT_SUB_STATUS',
                                   self.cmd_SET_PRINT_SUB_STATUS,
                                   desc=self.cmd_SET_PRINT_SUB_STATUS_help)
        self.gcode.register_command('PUSH_PRINT_STATUS',
                                   self.cmd_PUSH_PRINT_STATUS,
                                   desc=self.cmd_PUSH_PRINT_STATUS_help)
        self.gcode.register_command('POP_PRINT_STATUS',
                                   self.cmd_POP_PRINT_STATUS,
                                   desc=self.cmd_POP_PRINT_STATUS_help)
        
        # Register to receive status updates
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.printer.register_event_handler("gcode:command_error", self._handle_reset_stats)
        
        logging.info("PrintStatusManager initialized")

    def _handle_ready(self):
        # Initial status update
        self._update_status()
    
    def _handle_reset_stats(self):
        logging.info("检查到！！错误，恢复默认状态！！")
        self.set_main_status('ready') 

    def _update_status(self):
        # This method can be used to notify other components about status changes
        # For example, update the virtual_sdcard status
        pass

    def get_main_status(self):
        return self.current_main_status
    
    def get_sub_status(self):
        return self.current_sub_status

    def set_main_status(self, main_status, sub_status="", keep_sub=False):
        if main_status not in self.main_status_list:
            raise self.printer.command_error("Main status '%s' not valid" % main_status)
        
        old_main = self.current_main_status
        old_sub = self.current_sub_status
        
        main_changed = (main_status != old_main)
        sub_changed = (not keep_sub and sub_status != old_sub)
        if main_changed:
            if main_status == "printing":
                self.gcode.run_script_from_command(
                    "SET_TMC_FIELD STEPPER=stepper_z FIELD=tpwmthrs VELOCITY=0\n"
                    "SET_TMC_FIELD STEPPER=stepper_z1 FIELD=tpwmthrs VELOCITY=0")
            elif old_main == "printing":
                self.gcode.run_script_from_command(
                    "SET_TMC_FIELD STEPPER=stepper_z FIELD=tpwmthrs VELOCITY=9999999999\n"
                    "SET_TMC_FIELD STEPPER=stepper_z1 FIELD=tpwmthrs VELOCITY=9999999999")
        if main_changed or sub_changed:
            self.current_main_status = main_status
            self.current_step = 0
            if not keep_sub:
                self.current_sub_status = sub_status

            if main_changed:
                self.printer.send_event("print_stats_manager:main_stats_changed", 
                                        old_main, main_status)
            
            if sub_changed:
                self.printer.send_event("print_stats_manager:sub_stats_changed", 
                                        old_sub, sub_status)

            logging.info("Status changed: %s:%s -> %s:%s", 
                         old_main, old_sub, main_status, self.current_sub_status)

    def set_sub_status(self, sub_status):
        if sub_status != self.current_sub_status:
            if self.current_main_status in self.sub_status_list.keys():
                if sub_status not in self.sub_status_list[self.current_main_status]:
                    #raise self.printer.command_error("Sub status '%s' not valid for main status '%s'" % (sub_status, self.current_main_status))
                    self.gcode.respond_info("Sub status '%s' not valid for main status '%s'" % (sub_status, self.current_main_status))
                    return
            old_main = self.current_main_status
            old_sub = self.current_sub_status
            
            self.current_sub_status = sub_status
            self.current_step = self.current_step + 1
            self.printer.send_event("print_stats_manager:sub_stats_changed", 
                                        old_sub, sub_status)
            logging.info("Sub-status changed: %s:%s -> %s:%s",
                        old_main, old_sub, old_main, sub_status)

    def push_status(self):
        self.main_status_stack.append(self.current_main_status)
        self.sub_status_stack.append(self.current_sub_status)

    def pop_status(self):
        if not self.main_status_stack:
            return
        
        main_status = self.main_status_stack.pop()
        sub_status = self.sub_status_stack.pop()
        
        self.set_main_status(main_status, sub_status, keep_sub=True)


    def get_status(self, eventtime=None):
        return {
            'main_status': self.current_main_status,
            'sub_status': self.current_sub_status,
            'main_status_stack': list(self.main_status_stack),
            'sub_status_stack': list(self.sub_status_stack),
            "current_step": self.current_step
        }

    # GCode command implementations
    cmd_SET_PRINT_MAIN_STATUS_help = "Set the main print status"
    def cmd_SET_PRINT_MAIN_STATUS(self, gcmd):
        main_status = gcmd.get('MAIN_STATUS', '')
        sub_status = gcmd.get('SUB_STATUS', '')
        keep_sub = gcmd.get_int('KEEP_SUB', 0)
        
        self.set_main_status(main_status, sub_status, keep_sub)

    cmd_SET_PRINT_SUB_STATUS_help = "Set the sub print status"
    def cmd_SET_PRINT_SUB_STATUS(self, gcmd):
        sub_status = gcmd.get('SUB_STATUS', '')
        self.set_sub_status(sub_status)

    cmd_PUSH_PRINT_STATUS_help = "Push current status to stack"
    def cmd_PUSH_PRINT_STATUS(self, gcmd):
        self.push_status()

    cmd_POP_PRINT_STATUS_help = "Pop status from stack"
    def cmd_POP_PRINT_STATUS(self, gcmd):
        self.pop_status()

# This function is called by Klipper to load the module
def load_config(config):
    return PrintStatusManager(config)