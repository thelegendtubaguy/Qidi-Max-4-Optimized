# Upstream Klipper fixes and main-loop savings for QIDI Max 4 Optimized.
#
# QIDI's Klipper is upstream Klipper from August 2024 with QIDI's changes.
# Upstream has since fixed bugs in code QIDI left as it was. This module
# applies those fixes, and two cheaper versions of main-loop code, to QIDI's
# classes when Klipper loads it, each only when the function it replaces is
# exactly the one it was written for; otherwise that change is skipped and
# klippy.log says so.
#
# - Homing endstop sync (upstream 8e6e467eb): MCU_trsync.start scheduled
#   the trsync start and timeout messages for the time they take effect
#   instead of the move's start, so they could queue behind step messages.
#   They are now scheduled for the start, as upstream does.
# - MCU restarts (upstream 9ce631e8d): an MCU that restarted by itself called
#   invoke_async_shutdown without the details argument, so the shutdown
#   failed with an error in the serial thread and Klipper carried on until
#   a later, misleading error.
# - Lost MCUs (upstream 530a3560e, 9cb99754c, 013e44024): once Klipper
#   declares communication with an MCU lost, commands waiting for that MCU
#   to acknowledge them, and later ones, fail with "No communication with
#   MCU" instead of waiting forever while holding the G-code lock.
# - Garbage collection (upstream d57fe4395): objects that exist once Klipper
#   is ready are moved out of Python's garbage collector, so its full
#   collections have less to scan.
# - TMC drivers (upstream 8ea7be5dd): a stepper disable that arrives while
#   the driver is still being enabled waits for the enable to finish.
# - Heaters (upstream aae29ba48, 469124317): heater outputs turn off if
#   Klipper's main loop stops running for 5 s while the serial thread keeps
#   updating them, and a heater's temperature reads 0 only 7 s after its
#   last reading instead of 5 s, so a lost MCU is reported as such before
#   it looks like a heater fault.
# - Timers (upstream aa59b3203): update_timer no longer starts a timer's
#   callback again while an earlier run of it is paused.
# - Timer scan: the reactor keeps the next wake time in a local variable
#   while it checks its ~70 timers, instead of rewriting its own copy for
#   each one. The scan was about 3% of a core while printing.
# - Status updates: QIDI's once-a-second pass that sends Moonraker what
#   changed skips objects whose status is the same object as last time
#   (most gcode_macro objects), and runs QIDI's nested comparison of
#   multi_color_controller only on values that differ. Moonraker receives
#   the same updates.

import gc
import hashlib
import inspect
import logging

import mcu
import reactor
import serialhdl
import webhooks
from . import heaters, tmc

MARKER = "_tltg_klipper_fixes"
MAX_MAINTHREAD_TIME = 5.
QUELL_STALE_TIME = 7.
MAINTHREAD_INTERVAL = 1.
NO_COMMUNICATION = "No communication with MCU"

# SHA-256 of each replaced function's source, line endings removed, as
# shipped in QIDI firmware 01.01.07.01.
ORIGINALS = {
    "MCU_trsync.start":
        "13178b38e129d5f3ce64e1cccb65956176ff1a406d40dc30a503ca09248e0b92",
    "Printer.invoke_async_shutdown":
        "7f18957e5e8d95fafa7c2198deec95e8a7d35669308b2257ae45f855e10ae1b4",
    "SerialReader.raw_send_wait_ack":
        "094841940b9f9628c46dc5bed663cbf5d38d95b4b821aa8561c0c129c7e89e80",
    "SerialReader.disconnect":
        "ae066eddd47373d8ee04ca7ff85c12eff9d90c5dc61ddb1cc6a202d1a62925b3",
    "SerialReader.dump_debug":
        "149e814a8a11feb89bd968f203de678528db06ff0277543c3bda99d9765ab06f",
    "CommandWrapper.send_wait_ack":
        "421c202a4f53682354506437429159c7ed5e4ed986e18ce10192d87e4b0d547d",
    "MCU.check_active":
        "35a76e8a8d150833d710dd37691e507dac83a989d09484d805a36af8bcae24d7",
    "TMCCommandHelper._handle_stepper_enable":
        "2a77931ee40df077402b5eedd990fab96d8a3de3770773a0b620c98f74285749",
    "Heater.set_pwm":
        "62441a8a2df5ea7e63659165f1c37518681fc5fae0dd12f6c6d66658e788f6db",
    "Heater.get_temp":
        "13b71c06a60848fe38144f5477c4f88b17cb0721bdd52ed84db97a083a50ec52",
    "SelectReactor.update_timer":
        "63032501a62a442b80b518cd24d44d9409a7e65198467237ecebf2e788c42f8c",
    "SelectReactor._check_timers":
        "0ea257db086cd06aec86e30638ceda91ec100882268aa6a2b601e28f3f5cee02",
    "QueryStatusHelper._do_query":
        "9a74a0b5a7e416c0e682a081c2ba3103364397edb0d40cfad3dddbae166bd2e1",
}


def source_hash(func):
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        return None
    return hashlib.sha256(source.replace("\r", "").encode()).hexdigest()


def _replace(cls, name, label, new):
    """Put new on cls in place of name when the current one is QIDI's
    original. Returns True when the fix is in place."""
    current = cls.__dict__.get(name)
    if getattr(current, MARKER, False):
        return True
    if current is None or source_hash(current) != ORIGINALS[label]:
        return False
    setattr(new, MARKER, True)
    new.__name__ = name
    setattr(cls, name, new)
    return True


# ------------------------------------------------------------- homing sync
def _trsync_start(self, print_time, report_offset,
                  trigger_completion, expire_timeout):
    self._trigger_completion = trigger_completion
    self._home_end_clock = None
    clock = self._mcu.print_time_to_clock(print_time)
    expire_ticks = self._mcu.seconds_to_clock(expire_timeout)
    expire_clock = clock + expire_ticks
    report_ticks = self._mcu.seconds_to_clock(expire_timeout * .3)
    report_clock = clock + int(report_ticks * report_offset + .5)
    min_extend_ticks = int(report_ticks * .8 + .5)
    ffi_main, ffi_lib = mcu.chelper.get_ffi()
    ffi_lib.trdispatch_mcu_setup(self._trdispatch_mcu, clock, expire_clock,
                                 expire_ticks, min_extend_ticks)
    self._mcu.register_response(self._handle_trsync_state,
                                "trsync_state", self._oid)
    self._trsync_start_cmd.send([self._oid, report_clock, report_ticks,
                                 self.REASON_COMMS_TIMEOUT], reqclock=clock)
    for s in self._steppers:
        self._stepper_stop_cmd.send([s.get_oid(), self._oid])
    self._trsync_set_timeout_cmd.send([self._oid, expire_clock],
                                      reqclock=clock)


# ------------------------------------------------------------ MCU restarts
def _fix_async_shutdown(printer_cls):
    original = printer_cls.__dict__.get("invoke_async_shutdown")

    def invoke_async_shutdown(self, msg, details={}):
        return original(self, msg, details)
    return _replace(printer_cls, "invoke_async_shutdown",
                    "Printer.invoke_async_shutdown", invoke_async_shutdown)


# --------------------------------------------------------------- lost MCUs
def _abort_wait_acks(self):
    self._tltg_no_acks = True
    # The serial thread may be completing these, so work on a copy.
    for completion in list(self.pending_notifications.values()):
        completion.complete(None)


def _raw_send_wait_ack(self, cmd, minclock, reqclock, cmd_queue):
    if getattr(self, "_tltg_no_acks", False):
        self._error(NO_COMMUNICATION)
    self.last_notify_id += 1
    nid = self.last_notify_id
    completion = self.reactor.completion()
    self.pending_notifications[nid] = completion
    self.ffi_lib.serialqueue_send(self.serialqueue, cmd_queue,
                                  cmd, len(cmd), minclock, reqclock, nid)
    params = completion.wait()
    if params is None:
        self._error(NO_COMMUNICATION)
    return params


def _fix_disconnect():
    original = serialhdl.SerialReader.__dict__.get("disconnect")

    def disconnect(self):
        original(self)
        # Waits are possible again on the next connection.
        self._tltg_no_acks = False
    return _replace(serialhdl.SerialReader, "disconnect",
                    "SerialReader.disconnect", disconnect)


def _fix_dump_debug():
    original = serialhdl.SerialReader.__dict__.get("dump_debug")

    def dump_debug(self):
        if self.serialqueue is None:
            return ""
        return original(self)
    return _replace(serialhdl.SerialReader, "dump_debug",
                    "SerialReader.dump_debug", dump_debug)


def _send_wait_ack(self, data=(), minclock=0, reqclock=0):
    cmd = self._cmd.encode(data)
    try:
        self._serial.raw_send_wait_ack(cmd, minclock, reqclock,
                                       self._cmd_queue)
    except serialhdl.error as e:
        raise _COMMAND_ERROR[0](str(e))


_COMMAND_ERROR = [None]


def _fix_check_active():
    original = mcu.MCU.__dict__.get("check_active")

    def check_active(self, print_time, eventtime):
        was_timeout = self._is_timeout
        original(self, print_time, eventtime)
        if self._is_timeout and not was_timeout:
            _abort_wait_acks(self._serial)
    return _replace(mcu.MCU, "check_active", "MCU.check_active",
                    check_active)


def _fix_lost_mcus(printer):
    if ORIGINALS["SerialReader.raw_send_wait_ack"] != source_hash(
            serialhdl.SerialReader.__dict__.get("raw_send_wait_ack")) \
            and not getattr(serialhdl.SerialReader.__dict__.get(
                "raw_send_wait_ack"), MARKER, False):
        return False
    _COMMAND_ERROR[0] = printer.command_error
    return all((
        _replace(serialhdl.SerialReader, "raw_send_wait_ack",
                 "SerialReader.raw_send_wait_ack", _raw_send_wait_ack),
        _fix_disconnect(), _fix_dump_debug(),
        _replace(mcu.CommandWrapper, "send_wait_ack",
                 "CommandWrapper.send_wait_ack", _send_wait_ack),
        _fix_check_active()))


# ------------------------------------------------------------ TMC drivers
def _handle_stepper_enable(self, print_time, is_enable):
    mutex = self.__dict__.get("_tltg_enable_mutex")
    if mutex is None:
        mutex = self._tltg_enable_mutex = \
            self.printer.get_reactor().mutex()

    def enable_disable(eventtime):
        with mutex:
            if is_enable:
                self._do_enable(print_time)
            else:
                self._do_disable(print_time)
    self.printer.get_reactor().register_callback(enable_disable)


# ----------------------------------------------------------------- heaters
def _heater_set_pwm(self, read_time, value):
    # Heaters this module doesn't track have no deadline and keep QIDI's
    # behavior.
    deadline = getattr(self, "_tltg_mainthread_time", None)
    if self.target_temp <= 0. or self.is_shutdown \
            or (deadline is not None and read_time > deadline):
        value = 0.
    if ((read_time < self.next_pwm_time or not self.last_pwm_value)
            and abs(value - self.last_pwm_value) < 0.05):
        # No significant change in value - can suppress update
        return
    pwm_time = read_time + self.pwm_delay
    self.next_pwm_time = pwm_time + 0.75 * heaters.MAX_HEAT_TIME
    self.last_pwm_value = value
    self.mcu_pwm.set_pwm(pwm_time, value)


def _heater_get_temp(self, eventtime):
    est_print_time = self.mcu_pwm.get_mcu().estimated_print_time(eventtime)
    quell_time = est_print_time - QUELL_STALE_TIME
    with self.lock:
        if self.last_temp_time < quell_time:
            return 0., self.target_temp
        return self.smoothed_temp, self.target_temp


# ------------------------------------------------------------------ timers
def _update_timer(self, timer_handler, waketime):
    if getattr(timer_handler, "timer_is_running", False):
        return
    timer_handler.waketime = waketime
    self._next_timer = min(self._next_timer, waketime)


def _check_timers(self, eventtime, busy):
    if eventtime < self._next_timer:
        if busy:
            return 0.
        if self._check_gc:
            gi = gc.get_count()
            if gi[0] >= 700:
                # Reactor looks idle and gc is due - run it
                gc_level = 0
                if gi[1] >= 10:
                    gc_level = 1
                    if gi[2] >= 10:
                        gc_level = 2
                self._last_gc_times[gc_level] = eventtime
                gc.collect(gc_level)
                return 0.
        return min(1., max(.001, self._next_timer - eventtime))
    # Callbacks may lower self._next_timer; fold in the scan's minimum last.
    never = self._next_timer = self.NEVER
    next_timer = never
    g_dispatch = self._g_dispatch
    for t in self._timers:
        waketime = t.waketime
        if eventtime >= waketime:
            t.waketime = never
            t.timer_is_running = True
            t.waketime = waketime = t.callback(eventtime)
            t.timer_is_running = False
            if g_dispatch is not self._g_dispatch:
                self._next_timer = min(self._next_timer, next_timer, waketime)
                self._end_greenlet(g_dispatch)
                return 0.
        if waketime < next_timer:
            next_timer = waketime
    if next_timer < self._next_timer:
        self._next_timer = next_timer
    return 0.


# ------------------------------------------------------------------ status
def _status_diff(self, now, last):
    """QIDI's _get_diff_recursive, comparing each key's values in C first
    so that only values that differ go through QIDI's recursion."""
    if not isinstance(now, dict) or not isinstance(last, dict):
        return self._get_diff_recursive(now, last)
    diff = {}
    for k, v in now.items():
        if k not in last:
            diff[k] = v
        else:
            last_v = last[k]
            if v != last_v:
                res = self._get_diff_recursive(v, last_v)
                if res is not None:
                    diff[k] = res
    return diff if diff else None


def _do_query(self, eventtime):
    last_query = self.last_query
    query = self.last_query = {}
    msglist = self.pending_queries
    self.pending_queries = []
    msglist.extend(self.clients.values())
    lookup_object = self.printer.lookup_object
    deep_modules = webhooks.DEEP_COMPARISON_MODULES
    # Generate get_status() info for each client
    for cconn, subscription, send_func, template in msglist:
        is_query = cconn is None
        if not is_query and cconn.is_closed():
            del self.clients[cconn]
            continue
        # Query each requested printer object
        cquery = {}
        for obj_name, req_items in subscription.items():
            res = query.get(obj_name, None)
            if res is None:
                po = lookup_object(obj_name, None)
                if po is None or not hasattr(po, 'get_status'):
                    res = query[obj_name] = {}
                else:
                    res = query[obj_name] = po.get_status(eventtime)
            if req_items is None:
                req_items = list(res.keys())
                if req_items:
                    subscription[obj_name] = req_items
            if is_query:
                cquery[obj_name] = {ri: res.get(ri, None) for ri in req_items}
                continue
            lres = last_query.get(obj_name, {})
            if res is lres:
                # Every field is the same object as last time, so QIDI's
                # comparison would find no change.
                continue
            cres = {}
            if obj_name in deep_modules:
                for ri in req_items:
                    rd = res.get(ri, None)
                    last_val = lres.get(ri, None)
                    if rd != last_val:
                        diff_result = _status_diff(self, rd, last_val)
                        if diff_result is not None:
                            cres[ri] = diff_result
            else:
                for ri in req_items:
                    rd = res.get(ri, None)
                    if rd != lres.get(ri, None):
                        cres[ri] = rd
            if cres:
                cquery[obj_name] = cres
        # Send data
        if cquery or is_query:
            tmp = dict(template)
            tmp['params'] = {'eventtime': eventtime, 'status': cquery}
            send_func(tmp)
    if not query:
        # Unregister timer if there are no longer any subscriptions
        printer_reactor = self.printer.get_reactor()
        printer_reactor.unregister_timer(self.query_timer)
        self.query_timer = None
        return printer_reactor.NEVER
    return eventtime + webhooks.SUBSCRIPTION_REFRESH_TIME


class KlipperFixes:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.heaters = []
        fixes = [
            ("homing endstop sync", lambda: _replace(
                mcu.MCU_trsync, "start", "MCU_trsync.start", _trsync_start)),
            ("MCU restart shutdown",
             lambda: _fix_async_shutdown(type(self.printer))),
            ("lost MCU command waits", lambda: _fix_lost_mcus(self.printer)),
            ("TMC enable/disable order", lambda: _replace(
                tmc.TMCCommandHelper, "_handle_stepper_enable",
                "TMCCommandHelper._handle_stepper_enable",
                _handle_stepper_enable)),
            ("heater main-loop check", lambda: _replace(
                heaters.Heater, "set_pwm", "Heater.set_pwm",
                _heater_set_pwm)),
            ("heater stale temperature", lambda: _replace(
                heaters.Heater, "get_temp", "Heater.get_temp",
                _heater_get_temp)),
            ("timer double runs and scan", lambda: all((
                _replace(reactor.SelectReactor, "update_timer",
                         "SelectReactor.update_timer", _update_timer),
                _replace(reactor.SelectReactor, "_check_timers",
                         "SelectReactor._check_timers", _check_timers)))),
            ("status update pass", lambda: _replace(
                webhooks.QueryStatusHelper, "_do_query",
                "QueryStatusHelper._do_query", _do_query)),
        ]
        applied, skipped = [], []
        for name, fix in fixes:
            try:
                ok = fix()
            except Exception:
                logging.exception("tltg_klipper_fixes: %s failed", name)
                ok = False
            (applied if ok else skipped).append(name)
        self.mainthread_check = "heater main-loop check" in applied
        logging.info("tltg_klipper_fixes: applied %s", ", ".join(applied)
                     or "none")
        if skipped:
            logging.info("tltg_klipper_fixes: skipped %s; Klipper's code "
                         "differs from the version these fixes are for",
                         ", ".join(skipped))
        self.printer.register_event_handler("klippy:connect", self._connect)
        self.printer.register_event_handler("klippy:ready", self._ready)
        self.printer.register_event_handler("klippy:disconnect",
                                            self._disconnect)

    def _connect(self):
        pheaters = self.printer.lookup_object("heaters", None)
        self.heaters = [
            heater for heater in getattr(pheaters, "heaters", {}).values()
            if isinstance(heater, heaters.Heater)]

    def _ready(self):
        if self.mainthread_check:
            self.reactor.register_timer(self._note_mainthread,
                                        self.reactor.NOW)
        # Objects from startup are permanent; leave them out of collections.
        for generation in range(3):
            gc.collect(generation)
        gc.freeze()

    def _disconnect(self):
        gc.unfreeze()

    def _note_mainthread(self, eventtime):
        """Let heaters keep heating for the next 5 s: the main loop runs."""
        if self.printer.is_shutdown():
            for heater in self.heaters:
                heater._tltg_mainthread_time = -999.
            return self.reactor.NEVER
        for heater in self.heaters:
            try:
                est = heater.mcu_pwm.get_mcu().estimated_print_time(eventtime)
            except Exception:
                continue
            heater._tltg_mainthread_time = est + MAX_MAINTHREAD_TIME
        return eventtime + MAINTHREAD_INTERVAL


def load_config(config):
    return KlipperFixes(config)
