# QIDI Box feed motion for QIDI Max 4 Optimized.
#
# Wraps the vendor's three-stage load home and two-stage unload home on each
# `box_stepper slotN` so operators can set the fast push, approach speed, and
# acceleration through saved variables, globally or per slot. The vendor
# passes its profile as call arguments; settings that are absent keep those
# arguments unchanged. Plain do_home/do_move are not wrapped: they also run
# the load pre-stage, slot auto-load, and recovery.
#
# The unload's second extruder retract (`G1 E-120`) reads its length through
# box_extras.get_value_by_key("exl_2"); that lookup is wrapped to answer with
# the configured length. It is a global setting only.
#
# The effective per-slot motion is published as printer object status for
# Moonraker and Fluidd.

import hashlib
import logging
import math
import os
import re

# Named box_stepper.so builds, for reporting only: any QIDI Box code with the
# multi-step home methods is wrapped, and each call must still match the
# traced argument shape and look plausible before it is changed.
KNOWN_BUILDS = {
    "58ee8c61bffc3d4e18edc9e56a326495b6a218348bbfb13f7a012a946039b0a5":
        "01.01.07.01",
    "1d726c7b341f7acca85d0770c8966da236d02ca4a635e8a0b72bd40c3ea7df01":
        "01.01.06.05",
    "dcb6feb05a7254a2d96140ebb545d824b4633de92c0acf02793b96a882c2dfe1":
        "01.01.06.01-01.01.06.04",
}
# Vendor arguments traced live on 01.01.07.01. They stand in for the vendor
# baseline in status and validation until a load or unload supplies the real
# arguments; the wrappers always start from the arguments they receive.
VENDOR_BASELINE = {
    "load": (550, 380, 240, 85, 65, 10, 100),
    "unload": (-350, -1150, 65, 85, 100),
    "extruder_retract": 120,
}

# (key, saved variable, direction, minimum, maximum, unit). The command
# parameter is the upper-case key; a slot override appends "_slotN" to the
# saved variable.
SETTINGS = (
    ("fast_length", "tltg_box_load_fast_length", "load", 100, 2000, "mm"),
    ("fast_speed_1", "tltg_box_load_fast_speed_1", "load", 10, 150, "mm/s"),
    ("fast_speed_2", "tltg_box_load_fast_speed_2", "load", 10, 150, "mm/s"),
    ("approach_speed", "tltg_box_load_approach_speed", "load", 2, 40,
     "mm/s"),
    ("load_accel", "tltg_box_load_accel", "load", 20, 400, "mm/s\u00b2"),
    ("unload_speed_1", "tltg_box_unload_speed_1", "unload", 10, 150, "mm/s"),
    ("unload_speed_2", "tltg_box_unload_speed_2", "unload", 10, 150, "mm/s"),
    ("unload_accel", "tltg_box_unload_accel", "unload", 20, 400,
     "mm/s\u00b2"),
    ("unload_extruder_length", "tltg_box_unload_extruder_length", "retract",
     20, 300, "mm"),
)
# Settings that apply to every slot and take no SLOT= override.
GLOBAL_ONLY = ("unload_extruder_length",)
EXTRUDER_RETRACT_KEY = "exl_2"
VENDOR_KEY_PREFIXES = ("multi_extruder_load_", "multi_extruder_unload_",
                       EXTRUDER_RETRACT_KEY)
CLEAR_GLOBAL = ("vendor", "default", "none")
CLEAR_OVERRIDE = ("global",)


class ProfileError(Exception):
    pass


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _change_distance(speed_a, speed_b, accel):
    return abs(speed_a * speed_a - speed_b * speed_b) / (2. * accel)


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) \
        and math.isfinite(value)


def plausible_load(vendor):
    """True if the vendor's (l1, l2, l3, v1, v2, v3, accel) look as traced."""
    if len(vendor) != 7 or not all(_number(v) for v in vendor):
        return False
    l1, l2, l3, v1, v2, v3, accel = vendor
    return (50 <= l1 <= 3000 and 50 <= l2 <= 3000 and 10 <= l3 <= 3000
            and 0 < v3 < min(v1, v2) and max(v1, v2) <= 300
            and 10 <= accel <= 2000)


def plausible_unload(vendor):
    """True if the vendor's (l1, l2, v1, v2, accel) look as traced."""
    if len(vendor) != 5 or not all(_number(v) for v in vendor):
        return False
    l1, l2, v1, v2, accel = vendor
    return (-5000 <= l1 <= -50 and -5000 <= l2 <= -50 and 0 < v1 <= 300
            and 0 < v2 <= 300 and 10 <= accel <= 2000)


def _whole(value):
    """Return value as an int if it is a finite whole number, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (not math.isfinite(value)
                                     or value != int(value)):
        return None
    return int(value)


def _published(value):
    """Return a saved setting as JSON-safe status: int, None, or its repr."""
    if value is None:
        return None
    whole = _whole(value)
    return repr(value) if whole is None else whole


def override_name(name, slot):
    return "%s_%s" % (name, slot)


def slot_overrides(variables, slot):
    """Return {key: saved value} for the slot's overrides."""
    return {key: _published(variables.get(override_name(name, slot)))
            for key, name, _kind, _low, _high, _unit in SETTINGS
            if key not in GLOBAL_ONLY
            and variables.get(override_name(name, slot)) is not None}


def parse_settings(variables, direction, slot=None):
    """Return {key: int} for the settings a slot uses in one direction.

    A slot override wins over the global setting; unset settings are left
    out so the vendor argument applies. With slot None, only the global
    settings are read. Raises ProfileError naming the invalid variable.
    """
    values = {}
    for key, name, kind, low, high, _unit in SETTINGS:
        if kind != direction:
            continue
        if slot is not None and key not in GLOBAL_ONLY \
                and variables.get(override_name(name, slot)) is not None:
            name = override_name(name, slot)
        raw = variables.get(name)
        if raw is None:
            continue
        value = _whole(raw)
        if value is None or not low <= value <= high:
            raise ProfileError("%s must be a whole number from %d to %d"
                               % (name, low, high))
        values[key] = value
    return values


def load_profile(vendor, settings):
    """Map settings onto the vendor's (l1, l2, l3, v1, v2, v3, accel).

    Raises ProfileError if the combined profile cannot run on the vendor
    planner.
    """
    vl1, vl2, vl3, vv1, vv2, vv3, va = vendor
    if not settings:
        return tuple(vendor)
    v1 = settings.get("fast_speed_1", vv1)
    v2 = settings.get("fast_speed_2", vv2)
    v3 = settings.get("approach_speed", vv3)
    accel = settings.get("load_accel", va)
    vendor_fast = vl1 + vl2
    fast = settings.get("fast_length", vendor_fast)
    if v3 >= min(v1, v2):
        raise ProfileError("approach speed %d mm/s must be below both fast "
                           "stage speeds" % (v3,))
    reach_v1 = v1 * v1 / (2. * accel)
    l2_needed = (_change_distance(v1, v2, accel)
                 + _change_distance(v2, v3, accel))
    l2 = min(vl2, int(math.floor(fast - reach_v1)))
    if l2 < math.ceil(l2_needed):
        raise ProfileError(
            "fast push %d mm is too short for %d then %d mm/s, slowing to "
            "%d mm/s, at acceleration %d" % (fast, v1, v2, v3, accel))
    l1 = fast - l2
    l3 = vl3 + max(0, vendor_fast - fast)
    return (l1, l2, l3, v1, v2, v3, accel)


def unload_profile(vendor, settings):
    """Map settings onto the vendor's (l1, l2, v1, v2, accel)."""
    vl1, vl2, vv1, vv2, va = vendor
    if not settings:
        return tuple(vendor)
    v1 = settings.get("unload_speed_1", vv1)
    v2 = settings.get("unload_speed_2", vv2)
    accel = settings.get("unload_accel", va)
    if v1 == v2:
        raise ProfileError("unload speeds must differ (both %d mm/s)" % (v1,))
    if abs(vl1) < v1 * v1 / (2. * accel):
        raise ProfileError("unload stage 1 (%d mm) is too short to reach %d "
                           "mm/s at acceleration %d" % (abs(vl1), v1, accel))
    if abs(vl2) < (_change_distance(v1, v2, accel)
                   + v2 * v2 / (2. * accel)):
        raise ProfileError("unload stage 2 (%d mm) is too short for %d -> %d "
                           "mm/s at acceleration %d"
                           % (abs(vl2), v1, v2, accel))
    return (vl1, vl2, v1, v2, accel)


def plan_load(variables, slot, vendor):
    """Return (profile, state, error) for the slot's next load.

    State is vendor, custom, or error; on error the profile is the vendor's.
    With slot None this is the global profile.
    """
    vendor = tuple(vendor)
    try:
        profile = load_profile(vendor,
                               parse_settings(variables, "load", slot))
    except ProfileError as e:
        return vendor, "error", str(e)
    return profile, "vendor" if profile == vendor else "custom", None


def plan_unload(variables, slot, vendor):
    """Return (profile, state, error) for the slot's next unload."""
    vendor = tuple(vendor)
    try:
        settings = parse_settings(variables, "unload", slot)
        profile = unload_profile(vendor, settings)
    except ProfileError as e:
        return vendor, "error", str(e)
    return profile, "vendor" if profile == vendor else "custom", None


def extruder_retract(variables, default):
    """Return (length, error) for the unload's second extruder retract."""
    try:
        settings = parse_settings(variables, "retract")
    except ProfileError as e:
        return default, str(e)
    return settings.get("unload_extruder_length", default), None


def check_settings(variables, slot, vendor):
    """Raise ProfileError unless the settings a slot uses can run.

    Without an active integration (vendor None) only the values themselves
    are checked.
    """
    load = parse_settings(variables, "load", slot)
    unload = parse_settings(variables, "unload", slot)
    parse_settings(variables, "retract")
    if not vendor:
        return
    load_profile(vendor["load"], load)
    unload_profile(vendor["unload"], unload)


def _runs(variables, slot, vendor):
    try:
        check_settings(variables, slot, vendor)
    except ProfileError:
        return False
    return True


def vendor_values(vendor):
    l1, l2, l3, v1, v2, v3, accel = vendor["load"]
    u1, u2, uv1, uv2, uaccel = vendor["unload"]
    return {"fast_length": l1 + l2, "fast_speed_1": v1, "fast_speed_2": v2,
            "approach_speed": v3, "approach_length": l3, "load_accel": accel,
            "unload_speed_1": uv1, "unload_speed_2": uv2,
            "unload_accel": uaccel, "unload_length_1": abs(u1),
            "unload_length_2": abs(u2),
            "unload_extruder_length": vendor["extruder_retract"]}


class BoxFeedMotion:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.build = None
        self.vendor = None
        self.status = None
        self.slots = {}
        self._reported = set()
        self._status_cache = None
        self._set_status("waiting for Klipper to become ready")
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.gcode.register_command("TLTG_BOX_MOTION", self.cmd_TLTG_BOX_MOTION,
                                    desc=self.cmd_TLTG_BOX_MOTION_help)

    # ------------------------------------------------------------- variables
    def _raw_variables(self):
        save_vars = self.printer.lookup_object("save_variables", None)
        if save_vars is None:
            return None
        return getattr(save_vars, "allVariables", None)

    def _variables(self):
        return self._raw_variables() or {}

    def _save(self, name, value):
        save_vars = self.printer.lookup_object("save_variables", None)
        if save_vars is None:
            raise ProfileError("[save_variables] is not configured")
        gcmd = self.gcode.create_gcode_command(
            "SAVE_VARIABLE", "SAVE_VARIABLE",
            {"VARIABLE": name, "VALUE": repr(value)})
        save_vars.cmd_SAVE_VARIABLE(gcmd)

    def _report(self, message):
        logging.info("tltg_box_feed_motion: %s", message)
        if message in self._reported:
            return
        self._reported.add(message)
        self.gcode.respond_info("Box feed motion: %s" % (message,))

    def _slot_names(self):
        return sorted(self.slots, key=_slot_key)

    # ----------------------------------------------------------------- setup
    def _set_status(self, status):
        self.status = status
        self._status_cache = None
        logging.info("tltg_box_feed_motion: %s", status)

    def _handle_ready(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "box_stepper.so")
        try:
            digest = _hash_file(path)
            build = KNOWN_BUILDS.get(digest, "box_stepper.so %s" % (digest[:12],))
        except OSError:
            build = "box_stepper"
        slots = {}
        for name, obj in self.printer.lookup_objects("box_stepper"):
            methods = [getattr(obj, attr, None) for attr in
                       ("do_home_three_steps", "do_home_double_steps")]
            if not all(callable(m) for m in methods):
                continue
            slots[name.split()[-1]] = (obj, methods)
        if not slots:
            self._set_status("inactive: no QIDI Box slots found")
            return
        for slot, (obj, (load, unload)) in slots.items():
            obj.do_home_three_steps = self._wrap_load(slot, load)
            obj.do_home_double_steps = self._wrap_unload(slot, unload)
        extras = self.printer.lookup_object("box_extras", None)
        lookup = getattr(extras, "get_value_by_key", None)
        if callable(lookup):
            extras.get_value_by_key = self._wrap_lookup(lookup)
        else:
            logging.info("tltg_box_feed_motion: box_extras lookup not found; "
                         "extruder retract length is vendor")
        self.build = build
        self.vendor = dict(VENDOR_BASELINE)
        self.slots = slots
        self._set_status("active on %s, %d slots" % (build, len(slots)))
        vendor_keys = _vendor_keys(self._variables())
        if vendor_keys:
            logging.info("tltg_box_feed_motion: vendor motion keys saved: %s",
                         vendor_keys)

    # -------------------------------------------------------------- wrappers
    def _wrap_load(self, slot, original):
        def do_home_three_steps(*args, **kwargs):
            call_args = args
            try:
                if not kwargs and len(args) == 9 \
                        and _endstop_names(args[0]) == ["e_endstop"]:
                    vendor = tuple(args[1:8])
                    if plausible_load(vendor):
                        self._observe("load", vendor)
                        profile = self._load_for(slot, vendor)
                        call_args = (args[0],) + tuple(profile) + tuple(args[8:])
                    else:
                        self._report("load arguments %r are not as traced; "
                                     "vendor motion is unchanged" % (vendor,))
            except Exception:
                logging.exception("tltg_box_feed_motion: load profile failed")
            return original(*call_args, **kwargs)
        return do_home_three_steps

    def _wrap_lookup(self, original):
        def get_value_by_key(*args, **kwargs):
            value = original(*args, **kwargs)
            try:
                if not kwargs and len(args) == 2 \
                        and args[0] == EXTRUDER_RETRACT_KEY \
                        and _number(value) and 0 < value <= 1000:
                    self._observe("extruder_retract", value)
                    length, error = extruder_retract(self._variables(),
                                                     value)
                    if error is not None:
                        self._report("extruder retract uses the vendor "
                                     "length: %s" % (error,))
                    elif length != value:
                        logging.info("tltg_box_feed_motion: extruder retract "
                                     "%s mm (vendor %s)", length, value)
                        return length
            except Exception:
                logging.exception("tltg_box_feed_motion: extruder retract "
                                  "lookup failed")
            return value
        return get_value_by_key

    def _wrap_unload(self, slot, original):
        def do_home_double_steps(*args, **kwargs):
            call_args = args
            try:
                if not kwargs and len(args) == 7 \
                        and _endstop_names(args[0]) == ["b_endstop"]:
                    vendor = tuple(args[1:6])
                    if not plausible_unload(vendor):
                        self._report("unload arguments %r are not as traced; "
                                     "vendor motion is unchanged" % (vendor,))
                        return original(*args, **kwargs)
                    self._observe("unload", vendor)
                    profile, _state, error = plan_unload(self._variables(),
                                                         slot, vendor)
                    if error is not None:
                        self._report("%s unload uses vendor motion: %s"
                                     % (slot, error))
                    call_args = (args[0],) + tuple(profile) + tuple(args[6:])
                    if call_args != args:
                        logging.info("tltg_box_feed_motion: %s unload %s "
                                     "(vendor %s)", slot, profile, vendor)
            except Exception:
                logging.exception("tltg_box_feed_motion: unload profile failed")
            return original(*call_args, **kwargs)
        return do_home_double_steps

    def _observe(self, kind, value):
        """Use the vendor's actual arguments as the published baseline."""
        if self.vendor.get(kind) != value:
            self.vendor[kind] = value
            self._status_cache = None

    def _load_for(self, slot, vendor):
        vendor = tuple(vendor)
        profile, _state, error = plan_load(self._variables(), slot, vendor)
        if error is not None:
            self._report("%s load uses vendor motion: %s" % (slot, error))
        if profile != vendor:
            logging.info("tltg_box_feed_motion: %s load %s (vendor %s)",
                         slot, profile, vendor)
        return profile

    # ---------------------------------------------------------------- motion
    def _motion(self, variables, slot):
        """Return the published load and unload for a slot.

        With slot None this is the global profile, which slots without
        overrides use. Requires an active integration.
        """
        profile, state, error = plan_load(variables, slot,
                                          self.vendor["load"])
        l1, l2, l3, v1, v2, v3, accel = [int(v) for v in profile]
        unload, unload_state, unload_error = plan_unload(
            variables, slot, self.vendor["unload"])
        u1, u2, uv1, uv2, uaccel = [int(v) for v in unload]
        return {
            "overrides": slot_overrides(variables, slot) if slot else {},
            "load": {"state": state, "error": error, "fast_length": l1 + l2,
                     "fast_speed_1": v1, "fast_speed_2": v2,
                     "approach_speed": v3, "approach_length": l3,
                     "accel": accel},
            "unload": {"state": unload_state, "error": unload_error,
                       "speed_1": uv1, "speed_2": uv2, "accel": uaccel,
                       "length_1": abs(u1), "length_2": abs(u2)},
        }

    def _problems(self, variables):
        problems = []
        if self.vendor:
            motion = self._motion(variables, None)
            for direction in ("load", "unload"):
                if motion[direction]["error"] is not None:
                    problems.append("%s uses vendor motion: %s" % (
                        direction, motion[direction]["error"]))
            return problems + _retract_problems(variables)
        for direction in ("load", "unload"):
            try:
                parse_settings(variables, direction)
            except ProfileError as e:
                problems.append("%s uses vendor motion: %s" % (direction, e))
        return problems + _retract_problems(variables)

    # ---------------------------------------------------------------- status
    def get_status(self, eventtime=None):
        # QIDI's SAVE_VARIABLE replaces allVariables on every save, so an
        # unchanged dict object means unchanged settings.
        raw = self._raw_variables()
        cache = self._status_cache
        if cache is None or cache[0] is not raw:
            try:
                status = self._build_status(raw or {})
            except Exception:
                logging.exception("tltg_box_feed_motion: status failed")
                status = self._build_status({}, "status failed; see klippy.log")
            cache = self._status_cache = (raw, status)
        return cache[1]

    def _build_status(self, variables, problem=None):
        vendor = self.vendor
        status = {
            "active": vendor is not None,
            "status": self.status,
            "firmware": self.build,
            "limits": {key: {"min": low, "max": high, "unit": unit,
                             "direction": kind}
                       for key, _name, kind, low, high, unit in SETTINGS},
            "vendor": vendor_values(vendor) if vendor else None,
            "settings": {key: _published(variables.get(name))
                         for key, name, _kind, _low, _high, _unit in SETTINGS},
            "problems": [problem] if problem else self._problems(variables),
            "vendor_keys": _vendor_keys(variables),
            "slots": {},
        }
        if vendor:
            status["slots"] = {slot: self._motion(variables, slot)
                               for slot in self._slot_names()}
        return status

    # --------------------------------------------------------------- command
    cmd_TLTG_BOX_MOTION_help = ("Show or set QIDI Box load and unload motion "
                                "settings, globally or with SLOT= per slot")

    def cmd_TLTG_BOX_MOTION(self, gcmd):
        params = gcmd.get_command_parameters()
        slot = self._slot_param(gcmd) if "SLOT" in params else None
        variables = self._variables()
        changes = {}
        if gcmd.get_int("RESET", 0, minval=0, maxval=1):
            for key, name, _kind, _low, _high, _unit in SETTINGS:
                if slot is not None:
                    if key not in GLOBAL_ONLY:
                        changes[override_name(name, slot)] = None
                    continue
                changes[name] = None
                pattern = re.compile(re.escape(name) + r"_slot\d+$")
                changes.update((other, None) for other in variables
                               if pattern.match(other))
        clear, other = ((CLEAR_GLOBAL, CLEAR_OVERRIDE) if slot is None
                        else (CLEAR_OVERRIDE, CLEAR_GLOBAL))
        for key, name, _kind, low, high, _unit in SETTINGS:
            param = key.upper()
            if param not in params:
                continue
            if slot is not None and key in GLOBAL_ONLY:
                raise gcmd.error("%s applies to every slot; set it without "
                                 "SLOT" % (param,))
            target = name if slot is None else override_name(name, slot)
            raw = gcmd.get(param).strip().lower()
            if raw in clear:
                changes[target] = None
            elif slot is None and raw in other:
                raise gcmd.error("%s=%s needs SLOT; use %s=vendor to unset "
                                 "the global setting" % (param, raw, param))
            elif raw in other:
                raise gcmd.error("%s=%s is not available with SLOT; use "
                                 "%s=global to follow the global setting"
                                 % (param, raw, param))
            else:
                changes[target] = gcmd.get_int(param, minval=low, maxval=high)
        if changes:
            self._apply(gcmd, changes, slot)
        gcmd.respond_info(self._describe())

    def _slot_param(self, gcmd):
        raw = gcmd.get("SLOT").strip().lower()
        slot = raw if raw.startswith("slot") else "slot" + raw
        if slot not in self.slots:
            raise gcmd.error("Unknown Box slot '%s'" % (raw,))
        return slot

    def _apply(self, gcmd, changes, slot):
        current = self._variables()
        variables = dict(current)
        variables.update(changes)
        # A global change must keep the global profile and every overridden
        # slot that runs today runnable; a slot that already falls back
        # doesn't block it. Clearing a slot's overrides only returns it to the
        # global profile, which is checked when the globals change.
        if slot is None:
            targets = [None] + [s for s in self._slot_names()
                                if slot_overrides(variables, s)
                                and _runs(current, s, self.vendor)]
        elif any(value is not None for value in changes.values()):
            targets = [slot]
        else:
            targets = []
        for target in targets:
            try:
                check_settings(variables, target, self.vendor)
            except ProfileError as e:
                if target is None:
                    raise gcmd.error("Box feed motion not changed: %s" % (e,))
                raise gcmd.error("Box feed motion not changed: %s would use "
                                 "vendor motion: %s" % (target, e))
        for name, value in sorted(changes.items()):
            if current.get(name) != value:
                self._save(name, value)
        self._reported.clear()

    def _describe(self):
        variables = self._variables()
        lines = ["Box feed motion: %s" % (self.status,)]
        for title, kinds in (("Load", ("load",)),
                             ("Unload", ("retract", "unload"))):
            lines.append("%s: %s" % (title, _describe_values(
                {key: _published(variables.get(name))
                 for key, name, kind, _low, _high, _unit in SETTINGS
                 if kind in kinds}, "vendor")))
        if not self.vendor:
            lines.extend(self._problems(variables))
        else:
            motion = self._motion(variables, None)
            lines.append("Global load: %s" % (_describe_load(motion["load"]),))
            lines.append("Global unload: %s"
                         % (_describe_unload(motion["unload"]),))
            rest = []
            for slot in self._slot_names():
                motion = self._motion(variables, slot)
                overrides = motion["overrides"]
                if not overrides:
                    rest.append(slot)
                    continue
                parts = [_describe_values(overrides),
                         "load %s" % (_describe_load(motion["load"]),)]
                if any(key.startswith("unload_") for key in overrides):
                    parts.append("unload %s"
                                 % (_describe_unload(motion["unload"]),))
                lines.append("%s: %s" % (slot, "; ".join(parts)))
            if rest:
                lines.append("%s: global settings" % (_slot_ranges(rest),))
        vendor_keys = _vendor_keys(variables)
        if vendor_keys:
            lines.append("Vendor motion keys are saved and change the vendor "
                         "baseline: %s" % ", ".join(vendor_keys))
        return "\n".join(lines)


def _retract_problems(variables):
    error = extruder_retract(variables, None)[1]
    return [] if error is None else [
        "extruder retract uses the vendor length: %s" % (error,)]


def _vendor_keys(variables):
    return sorted("%s=%r" % (name, value) for name, value in variables.items()
                  if name.startswith(VENDOR_KEY_PREFIXES))


def _slot_key(slot):
    number = slot[len("slot"):]
    return (0, int(number), "") if number.isdigit() else (1, 0, slot)


def _slot_ranges(slots):
    """Name slots, folding runs of three or more consecutive numbers."""
    names, run = [], []

    def flush():
        if len(run) >= 3:
            names.append("%s\u2013%s" % (run[0][1], run[-1][1]))
        else:
            names.extend(slot for _number, slot in run)
        del run[:]
    for slot in sorted(slots, key=_slot_key):
        order, number, _name = _slot_key(slot)
        if order:
            flush()
            names.append(slot)
            continue
        if run and number != run[-1][0] + 1:
            flush()
        run.append((number, slot))
    flush()
    return ", ".join(names)


def _describe_values(values, unset=None):
    return " ".join("%s=%s" % (key.upper(), unset if value is None else value)
                    for key, value in values.items())


def _describe_load(load):
    if load["state"] == "error":
        return "vendor motion (%s)" % (load["error"],)
    return ("fast %d mm at %d/%d mm/s, approach up to %d mm at %d mm/s, "
            "accel %d" % (load["fast_length"], load["fast_speed_1"],
                          load["fast_speed_2"], load["approach_length"],
                          load["approach_speed"], load["accel"]))


def _describe_unload(unload):
    if unload["state"] == "error":
        return "vendor motion (%s)" % (unload["error"],)
    return ("%d mm at %d mm/s, %d mm at %d mm/s, accel %d"
            % (unload["length_1"], unload["speed_1"], unload["length_2"],
               unload["speed_2"], unload["accel"]))


def _endstop_names(endstops):
    try:
        return [name for _endstop, name in endstops]
    except Exception:
        return None



def load_config(config):
    return BoxFeedMotion(config)
