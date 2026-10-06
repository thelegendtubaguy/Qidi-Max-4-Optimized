

class WarmTrialCapture(QidiRawCapture):
    def __init__(self, printer):
        super().__init__(printer)
        self.motion = None
        self.last_guard = float('-inf')

    def _cold_idle(self):
        now = self.reactor.monotonic()
        if self.cancelled or self.printer.is_shutdown():
            raise CalibrationError("WARM_TRIAL_SHUTDOWN")
        if now - self.last_guard < 0.1:
            return
        state = self.printer.lookup_object("print_stats").get_status(now)["state"]
        if state not in SAFE_PRINT_STATES:
            raise CalibrationError("WARM_TRIAL_ACTIVE_PRINT")
        idle = self.printer.lookup_object("idle_timeout").get_status(now)["state"]
        if idle not in SAFE_IDLE_TIMEOUT_STATES and not (self.motion is not None and idle == "Printing"):
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
        self.last_guard = now

    def _exchange(self, kind, ordinal):
        if kind == "raw" and ordinal == 20:
            self._cold_idle()
            self._check()
            toolhead = self.printer.lookup_object("toolhead")
            now = self.reactor.monotonic()
            self.motion = {"segments": [], "host_anchor_offset": now-self.start,
                           "print_anchor": toolhead.get_status(now)["estimated_print_time"],
                           "ordinary_e_only_not_pa_eligible": True}
            gcode = self.printer.lookup_object("gcode")
            commands = ["M83"]
            for speed in (0.4, 1.2, 0.4, 1.2, 0.4):
                commands.append("G1 E%.6f F%.6f" % (speed*0.3, speed*60))
                self.motion["segments"].append({"speed_mm_s": speed, "extrusion_mm": speed*0.3,
                                                "nominal_seconds": 0.3})
            self.motion["start_print_time_before_flush"] = toolhead.get_last_move_time()
            gcode.run_script_from_command("\n".join(commands))
            self.motion["end_print_time"] = toolhead.get_last_move_time()
            self.motion["extrusion_mm"] = 1.08
            self.motion["segment_boundary_times_are_nominal"] = True
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
        try:
            capture = WarmTrialCapture(self.printer)
            capture._cold_idle()
        except Exception as exc:
            self.printer.lookup_object("heaters").turn_off_all_heaters()
            raise gcmd.error(str(exc))
        self.used = True
        result = {"complete": False, "temperature": 245, "nozzle": 0.4,
                  "material": "PETG", "cleanup_complete": False}
        toolhead = self.printer.lookup_object("toolhead")
        now = self.printer.get_reactor().monotonic()
        original = toolhead.get_status(now)
        self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=TLTG_WARM_TRIAL_STATE")
        try:
            result["capture"] = capture.capture(400, 250, 0.1)
            result["motion"] = capture.motion
            result["complete"] = result["capture"]["complete"]
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            try:
                if not self.printer.is_shutdown():
                    toolhead.wait_moves()
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
