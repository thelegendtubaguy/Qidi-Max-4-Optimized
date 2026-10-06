

class WarmTrialCapture(QidiRawCapture):
    def __init__(self, printer):
        super().__init__(printer)
        self.motion = None
        self.pa_prepared = False
        self.adapter = QidiDirectTrapqAdapter(printer)

    def _cold_idle(self):
        now = self.reactor.monotonic()
        if self.cancelled or self.printer.is_shutdown():
            raise CalibrationError("WARM_TRIAL_SHUTDOWN")
        state = self.printer.lookup_object("print_stats").get_status(now)["state"]
        if state not in SAFE_PRINT_STATES:
            raise CalibrationError("WARM_TRIAL_ACTIVE_PRINT")
        idle = self.printer.lookup_object("idle_timeout").get_status(now)["state"]
        if idle not in SAFE_IDLE_TIMEOUT_STATES and not ((self.motion is not None or self.pa_prepared) and idle == "Printing"):
            raise CalibrationError("WARM_TRIAL_UNOWNED_MOTION")
        toolhead = self.printer.lookup_object("toolhead")
        status = toolhead.get_status(now)
        if status["homed_axes"] != "xyz":
            raise CalibrationError("WARM_TRIAL_REQUIRES_HOMING")
        if any(abs(a-b) > 0.1 for a,b in zip(status["position"][:3], (135,403,200))):
            raise CalibrationError("WARM_TRIAL_REQUIRES_CHUTE")
        heaters = self.printer.lookup_object("heaters").get_status(now)
        for name in heaters["available_heaters"]:
            heater = self.printer.lookup_object(name).get_status(now)
            if name == "extruder":
                if heater["target"] != 245 or not 240 <= heater["temperature"] <= 250 or not heater["can_extrude"]:
                    raise CalibrationError("WARM_TRIAL_TEMPERATURE")
            elif heater["target"] != 0:
                raise CalibrationError("WARM_TRIAL_OTHER_HEATER")
        inspect_loaded_filament(self.printer, now)

    def _exchange(self, kind, ordinal):
        if kind == "raw" and ordinal == 20:
            self._cold_idle()
            self._check()
            toolhead = self.printer.lookup_object("toolhead")
            toolhead.flush_step_generation()
            self.adapter._validate_nominal_state()
            extruder = self.adapter.extruder
            if not extruder.heater.can_extrude or extruder.max_e_velocity < 1 or extruder.max_e_accel < 10 or extruder.max_e_dist < 2:
                raise CalibrationError("PA_TRIAL_EXTRUDER_LIMIT")
            start = max(toolhead.get_last_move_time(), toolhead.get_status(self.reactor.monotonic())["estimated_print_time"]) + 0.2
            start_e = toolhead.commanded_pos[3]
            move = TrapqMove(start, 0.1, 1.9, 0.1, start_e, 0.0, 1.0, 10.0)
            assert abs(move.distance - 2.0) < 1e-9
            end = start + 2.1
            self.motion = {"start_print_time": start, "end_print_time": end,
                           "host_queued_offset": self.reactor.monotonic()-self.start,
                           "extrusion_mm": 2, "speed_mm_s": 1,
                           "acceleration_mm_s2": 10, "pa_eligible": True}
            move.append(extruder)
            extruder.last_position = start_e + 2.0
            toolhead.commanded_pos[3] = start_e + 2.0
            toolhead.note_mcu_movequeue_activity(end + toolhead.kin_flush_delay, set_step_gen_time=True)
            toolhead._advance_move_time(end + toolhead.kin_flush_delay)
            self.printer.lookup_object("gcode_move").reset_last_position()
        return super()._exchange(kind, ordinal)


class WarmTrial:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.used = False
        self.gcode.register_command("_TLTG_WARM_TRIAL", self.run)

    def run(self, gcmd):
        if self.used:
            raise gcmd.error("WARM_TRIAL_PROCESS_RESTART_REQUIRED")
        k = gcmd.get_float("K", minval=0, maxval=0.05)
        if k not in (0.0, 0.05):
            raise gcmd.error("PA_TRIAL_K_MUST_BE_0_OR_0_05")
        try:
            capture = WarmTrialCapture(self.printer)
            capture._cold_idle()
        except Exception as exc:
            self.printer.lookup_object("heaters").turn_off_all_heaters()
            raise gcmd.error(str(exc))
        self.used = True
        result = {"complete": False, "temperature": 245, "nozzle": 0.4,
                  "material": "PETG", "tested_k": k, "cleanup_complete": False}
        toolhead = self.printer.lookup_object("toolhead")
        now = self.printer.get_reactor().monotonic()
        original = toolhead.get_status(now)
        extruder_status = toolhead.get_extruder().get_status(now)
        self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=TLTG_WARM_TRIAL_STATE")
        try:
            capture.pa_prepared = True
            self.gcode.run_script_from_command("SET_PRESSURE_ADVANCE ADVANCE=%s SMOOTH_TIME=0.03" % k)
            result["capture"] = capture.capture(100, 40, 0.1)
            result["motion"] = capture.motion
            result["complete"] = result["capture"]["complete"]
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            try:
                if not self.printer.is_shutdown():
                    toolhead.wait_moves()
                    self.gcode.run_script_from_command("SET_PRESSURE_ADVANCE ADVANCE=%s SMOOTH_TIME=%s" % (extruder_status["pressure_advance"], extruder_status["smooth_time"]))
                    if capture.motion is not None:
                        self.gcode.run_script_from_command("CLEAR_OOZE\nCLEAR_FLUSH\nM400")
                    self.gcode.run_script_from_command(
                        "RESTORE_GCODE_STATE NAME=TLTG_WARM_TRIAL_STATE MOVE=0\n"
                        "SET_VELOCITY_LIMIT VELOCITY=%s ACCEL=%s MINIMUM_CRUISE_RATIO=%s SQUARE_CORNER_VELOCITY=%s" %
                        (original["max_velocity"],original["max_accel"],original["minimum_cruise_ratio"],original["square_corner_velocity"]))
                    result["cleanup_complete"] = True
            except Exception as exc:
                result["cleanup_error"] = str(exc)
            finally:
                self.printer.lookup_object("heaters").turn_off_all_heaters()
                with tempfile.NamedTemporaryFile(mode="w", prefix="tltg_warm_trial_", suffix=".json", delete=False) as f:
                    json.dump(result, f)
                gcmd.respond_info("WARM_TRIAL_ARTIFACT=" + f.name)
        if not result["complete"] or not result["cleanup_complete"]:
            raise gcmd.error("WARM_TRIAL_INCOMPLETE_SEE_ARTIFACT")


def load_config(config):
    return WarmTrial(config)
