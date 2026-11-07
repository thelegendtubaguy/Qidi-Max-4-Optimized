# Klipper main-loop health for Valve Oil.
#
# QIDI's box_extras checks each Box load with the toolhead load cell.
# auto_detect_filament_advance registers _init_probe_data_advance, which
# samples the load cell every 0.2 s for a resting baseline and then stops;
# detect_filament_loaded registers _read_wei_timer, which watches for the
# force jump of filament reaching the nozzle while the extruder pushes, and
# stops it once the load is done or the next check starts. QIDI then drops
# its reference to the stopped timer but never unregisters it, so every load
# leaves its timers in Klipper's list, three per load on the test printer.
# Klipper walks that whole list on every pass of its main loop: after 405
# loads it held 1278 timers, its main thread was busy most of the time even
# while idle, and a Box motor move missed the 50 ms window its endstop sync
# allows ("Communication timeout during homing"), ending a print.
#
# This module unregisters those timers once they can never run again: their
# callback is one of QIDI's two load-cell callbacks, they are stopped, and
# the QIDI object no longer holds them. It also measures how busy Klipper's
# main thread is and how late its timers run, warns when timers keep piling
# up or the main loop stays saturated, and logs that context when an
# endstop sync times out, so the next such failure explains itself. QIDI's
# load-cell probe (probe_air, extras/air) reports a failed endstop sync as
# "WEIGHT sensor error", the timeout included; the THR firmware never sends
# the probe's own sensor-error reason, so that error gets the context too. Its
# status feeds the timer count and main-thread load to Fluidd's System
# Utilization charts.
#
# Endstop syncs: a homing move across boards stays armed only while each
# board's status reports, sent every 30% of the sync timeout (15 ms for
# QIDI's 50 ms), keep reaching Klipper, whose serial thread, not its main
# thread, renews the timeout on the other boards. Each sync here keeps its
# last reports, with the board's clock when it sent each one and Klipper's
# time when its serial thread read it, and its final result. A failed sync
# then says which board timed out, and whether a board sent its reports late
# or they reached Klipper late.
#
# Status copies: QIDI's multi_color_controller status, which Moonraker reads
# every second, deep-copies its flattened Box status, a dict of about 440
# strings, numbers, and lists, which takes about half of the status's 11 ms.
# Klipper's macros deep-copy each object's whole status the first time a
# macro reads it, such as 48 ms for printer.configfile, which QIDI's start,
# end, and startup macros read many times. In both modules copy.deepcopy is
# replaced with a plain copy of the same dicts, lists, tuples, and values,
# several times faster; anything else still goes to copy.deepcopy.
#
# Late MCU commands: a command that takes effect at an MCU clock, such as a
# pin change or an endstop sync's timeout, must reach the MCU before that
# clock. QIDI's Max 4 mainboard runs one that arrives late at once and logs
# "Timer too close" to klippy.log, which names neither the command nor what
# sent it. Each command whose format has a clock is checked as Klipper sends
# it: when its clock is already past, or nearly so, by the MCU's estimated
# time, or by the clock of an earlier command on its queue that it must wait
# for, klippy.log gets a warning naming the MCU, the command, how late it
# is, and the Python calls that sent it. Other commands are not wrapped.
# Steps go out from Klipper's C code and are not checked.

import collections
import copy
import logging
import os
import sys
import time
import traceback
import types

# QIDI box_extras / box2base load-cell callbacks whose stopped timers leak.
FINISHED_CALLBACKS = ("_read_wei_timer", "_init_probe_data_advance")
CLEANUP_INTERVAL = 5.
SAMPLE_INTERVAL = 1.
REPORT_INTERVAL = 60.
# Samples kept: enough for the busy window.
HISTORY = 300
# Klipper's timer count settles within a minute of starting; warn when it
# grows this far past that.
TIMER_GROWTH_WARNING = 50
# Warn when the main thread is at least this busy over the whole window.
# Printing and Box tool changes peak near 25% over five minutes on the test
# printer; the leaked timers had it near 50% when a Box unload timed out.
BUSY_LOAD = 0.45
BUSY_WINDOW = 300.
WARNING_REPEAT = 3600.
# Window before an endstop sync timeout reported with it.
TIMEOUT_CONTEXT = 10.
HOMING_TIMEOUT = "Communication timeout during homing"
PROBE_SYNC_ERROR = "WEIGHT sensor error"
PROBE_SYNC_FAILURE = ("Load-cell probe endstop sync failure (QIDI reports it "
                      "as \"%s\")" % (PROBE_SYNC_ERROR,))
# Status reports kept per endstop sync, about a second of QIDI's, and how
# many of them klippy.log gets after a failure.
SYNC_REPORTS = 64
SYNC_REPORTS_LOGGED = 12
# Objects whose modules deep-copy whole statuses: QIDI's Box status, and
# Klipper's macro access to every object's status.
STATUS_COPIERS = ("multi_color_controller", "gcode_macro")
# Command parameters holding the MCU clock a command takes effect at.
CLOCK_PARAMS = ("clock", "report_clock")
# A command less than this ahead of its MCU when sent is reported: the
# mainboard link's round trip alone is about 1 ms.
LATE_COMMAND_MARGIN = 0.005
# Each MCU's command is reported at most this often; the next report counts
# the ones in between.
LATE_COMMAND_REPEAT = 10.
# Python calls listed with a late command, innermost first.
LATE_COMMAND_STACK = 8

# The KlipperHealth of the running Klipper; the endstop wrapper outlives a
# RESTART, which creates a new one.
_current = [None]


def _held_ids(owner):
    """Ids of the objects an owner holds in its attributes, one level into
    containers."""
    held = set()
    try:
        values = list(vars(owner).values())
    except TypeError:
        return held
    for value in values:
        held.add(id(value))
        if isinstance(value, dict):
            held.update(id(v) for v in value.values())
        elif isinstance(value, (list, tuple, set)):
            held.update(id(v) for v in value)
    return held


def finished_timers(reactor):
    """QIDI load-cell timers that can never run again."""
    timers = getattr(reactor, "_timers", None)
    if not isinstance(timers, list):
        return []
    found = []
    held = {}
    for timer in timers:
        callback = getattr(timer, "callback", None)
        if getattr(callback, "__name__", None) not in FINISHED_CALLBACKS \
                or getattr(timer, "waketime", None) != reactor.NEVER:
            continue
        owner = getattr(callback, "__self__", None)
        if owner is None:
            continue
        if id(owner) not in held:
            held[id(owner)] = _held_ids(owner)
        if id(timer) not in held[id(owner)]:
            found.append(timer)
    return found


def _wrap_trsync(cls):
    """Make cls, Klipper's MCU_trsync, keep its recent status reports and
    final result for each sync. Returns True when it does."""
    start = getattr(cls, "start", None)
    handle = getattr(cls, "_handle_trsync_state", None)
    stop = getattr(cls, "stop", None)
    if start is None or handle is None or stop is None:
        return False
    if getattr(handle, "_tltg_klipper_health", False):
        return True

    def start_sync(trsync, *args, **kwargs):
        timeout = args[3] if len(args) > 3 else kwargs.get("expire_timeout")
        trsync._tltg_sync = {"timeout": timeout, "result": None,
                             "reports": collections.deque(maxlen=SYNC_REPORTS)}
        return start(trsync, *args, **kwargs)

    # Runs on the board's serial thread.
    def handle_report(trsync, params):
        sync = getattr(trsync, "_tltg_sync", None)
        if sync is not None:
            sync["reports"].append((
                params.get("#receive_time"), params.get("clock"),
                params.get("can_trigger"), params.get("trigger_reason")))
        return handle(trsync, params)

    def stop_sync(trsync, *args, **kwargs):
        result = stop(trsync, *args, **kwargs)
        sync = getattr(trsync, "_tltg_sync", None)
        if sync is not None:
            sync["result"] = result
        return result

    handle_report._tltg_klipper_health = True
    cls.start = start_sync
    cls._handle_trsync_state = handle_report
    cls.stop = stop_sync
    return True


def _endstop_trsyncs(endstop):
    """(MCU name, trsync or None) for each board in an endstop's sync."""
    found = []
    dispatch = getattr(endstop, "_dispatch", None)
    for trsync in getattr(dispatch, "_trsyncs", None) or ():
        try:
            found.append((trsync.get_mcu().get_name(), trsync))
        except Exception:
            pass
    if not found:
        try:
            found.append((endstop.get_mcu().get_name(), None))
        except Exception:
            pass
    return found


def send_gaps(reports, freq):
    """Seconds since the board sent its previous status report, for each
    report, or None where either has no send time: the report answering
    Klipper's own trigger request carries clock 0."""
    gaps, previous = [], None
    for _receive_time, clock, can_trigger, _reason in reports:
        if clock is None or not (can_trigger or clock):
            clock = None
        gaps.append(None if clock is None or previous is None
                    else ((clock - previous) & 0xffffffff) / freq)
        previous = clock
    return gaps


def _sync_detail(trsyncs):
    """The console summary of a failed sync's status reports, and the
    klippy.log list of each board's last reports."""
    timed_out, gaps, logged = [], [], []
    syncs = [(name, trsync, getattr(trsync, "_tltg_sync", None))
             for name, trsync in trsyncs]
    syncs = [(name, trsync, sync) for name, trsync, sync in syncs if sync]
    if not syncs:
        return "", ""
    times = [r[0] for _, _, sync in syncs for r in sync["reports"]
             if r[0] is not None]
    last = max(times) if times else None
    timeout = None
    for name, trsync, sync in syncs:
        timeout = timeout or sync["timeout"]
        limit = getattr(trsync, "REASON_COMMS_TIMEOUT", None)
        if limit is not None and sync["result"] is not None \
                and sync["result"] >= limit:
            timed_out.append(name)
        reports = list(sync["reports"])
        try:
            freq = float(trsync.get_mcu().seconds_to_clock(1.))
        except Exception:
            continue
        sent = send_gaps(reports, freq)
        if len(reports) >= 2:
            received = [b[0] - a[0] for a, b in zip(reports, reports[1:])
                        if a[0] is not None and b[0] is not None]
            gaps.append("%s sent them up to %d ms apart and Klipper read them "
                        "up to %d ms apart"
                        % (name, round(max([g for g in sent if g] or [0.])
                                       * 1000),
                           round(max(received or [0.]) * 1000)))
        entries = []
        for (receive_time, _clock, can_trigger, reason), gap in zip(
                reports[-SYNC_REPORTS_LOGGED:], sent[-SYNC_REPORTS_LOGGED:]):
            entry = ("%.1f" % ((receive_time - last) * 1000.)
                     if receive_time is not None and last is not None
                     else "?")
            if gap is not None:
                entry += "/%.1f" % (gap * 1000.,)
            if not can_trigger:
                entry += " reason=%s" % (reason,)
            entries.append(entry)
        logged.append("%s (%d reports, result %s): %s"
                      % (name, len(sync["reports"]), sync["result"],
                         " ".join(entries) or "none"))
    summary = ""
    if timed_out:
        summary += " The sync timed out on %s" % (" and ".join(timed_out),)
        if timeout:
            summary += " (%d ms limit)" % (round(timeout * 1000),)
        summary += "."
    if gaps:
        summary += " Of its status reports, %s." % ("; ".join(gaps),)
    detail = ("endstop sync status reports, as ms read before the last one "
              "/ ms since the board sent its previous one: %s"
              % ("; ".join(logged),))
    return summary, detail


def _wrap_home_wait(cls, error, failure):
    """Make cls.home_wait report the context of an endstop sync failure,
    which it raises with error in the message. Returns True when it does."""
    original = getattr(cls, "home_wait", None)
    if original is None:
        return False
    if getattr(original, "_tltg_klipper_health", False):
        return True

    def home_wait(endstop, *args, **kwargs):
        try:
            return original(endstop, *args, **kwargs)
        except Exception as e:
            health = _current[0]
            if health is not None and error in str(e):
                try:
                    health.note_homing_timeout(failure,
                                               _endstop_trsyncs(endstop))
                except Exception:
                    logging.exception("tltg_klipper_health: homing timeout "
                                      "report failed")
            raise
    home_wait._tltg_klipper_health = True
    cls.home_wait = home_wait
    return True


def _late_command(mcu, command, ahead):
    health = _current[0]
    if health is None:
        return
    try:
        # The caller of the command's send.
        health.note_late_command(mcu.get_name(), command, ahead,
                                 sys._getframe(2))
    except Exception:
        logging.exception("tltg_klipper_health: late command report failed")


def watch_command(mcu, command, msgformat):
    """Check each send of an MCU command whose format has a clock. Returns
    True when its sends are checked."""
    parts = msgformat.split()
    index = next((i for i, arg in enumerate(parts[1:])
                  if arg.split("=")[0] in CLOCK_PARAMS), None)
    send = getattr(command, "send", None)
    get_clock = getattr(getattr(mcu, "_clocksync", None), "get_clock", None)
    if index is None or send is None or get_clock is None:
        return False
    freq = float(mcu.seconds_to_clock(1.))
    if freq <= 0.:
        return False
    monotonic = mcu.get_printer().get_reactor().monotonic
    margin = LATE_COMMAND_MARGIN * freq
    name = parts[0]

    def send_checked(data=(), minclock=0, reqclock=0):
        try:
            clock = data[index]
        except (IndexError, KeyError, TypeError):
            clock = 0
        # Clock 0 stops a command, such as an endstop check, instead.
        if clock:
            now = get_clock(monotonic())
            # Ticks ahead of the MCU, negative when past, in 32 bits as the
            # MCU compares them.
            ahead = (((clock - now + 0x80000000) & 0xffffffff) - 0x80000000)
            # Klipper holds the command until minclock, a full host clock
            # that can be any time before the command's own.
            ahead -= max(0, minclock - now)
            if ahead < margin:
                _late_command(mcu, name, ahead / freq)
        return send(data, minclock, reqclock)
    command.send = send_checked
    return True


def _watch_late_commands(cls):
    """Make cls, Klipper's MCU, check the commands it looks up that have a
    clock. Returns True when it does."""
    lookups = [(name, getattr(cls, name, None))
               for name in ("lookup_command", "lookup_query_command")]
    if any(lookup is None for _name, lookup in lookups):
        return False

    def wrap(lookup):
        if getattr(lookup, "_tltg_klipper_health", False):
            return lookup

        def lookup_watched(mcu, msgformat, *args, **kwargs):
            command = lookup(mcu, msgformat, *args, **kwargs)
            try:
                watch_command(mcu, command, msgformat)
            except Exception:
                logging.exception("tltg_klipper_health: cannot check %s",
                                  msgformat)
            return command
        lookup_watched._tltg_klipper_health = True
        return lookup_watched
    for name, lookup in lookups:
        setattr(cls, name, wrap(lookup))
    return True


_PLAIN_VALUES = (str, int, float, bool, type(None))


def _plain_copy(value):
    kind = type(value)
    if kind in _PLAIN_VALUES:
        return value
    if kind is dict:
        return {key: _plain_copy(item) for key, item in value.items()}
    if kind is list:
        return [_plain_copy(item) for item in value]
    if isinstance(value, tuple):
        # As copy.deepcopy: a tuple, or a named tuple such as Klipper's
        # Coord, whose items copy to themselves is returned as it is.
        items = [_plain_copy(item) for item in value]
        if all(new is old for new, old in zip(items, value)):
            return value
        if kind is tuple:
            return tuple(items)
    raise TypeError(kind)


def _deepcopy(value, memo=None, *args):
    """copy.deepcopy for status trees of plain values, copied directly."""
    if memo is None:
        try:
            return _plain_copy(value)
        except (TypeError, RecursionError):
            pass
    return copy.deepcopy(value, memo, *args)


def _plain_copy_module():
    module = types.ModuleType("copy")
    module.__dict__.update(copy.__dict__)
    module.deepcopy = _deepcopy
    return module


def lighten_status_copy(obj):
    """Give the module that defines obj's class the plain-value deepcopy.
    Returns True when it has it."""
    module = sys.modules.get(getattr(type(obj), "__module__", None))
    current = getattr(module, "copy", None)
    if getattr(current, "deepcopy", None) is _deepcopy:
        return True
    if current is not copy:
        return False
    module.copy = _plain_copy_module()
    return True


class KlipperHealth:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.removed = 0
        self.timer_baseline = None
        self.samples = collections.deque(maxlen=HISTORY)
        self.last_warning = {}
        self.late_commands = {}
        self._next_cleanup = 0.
        self._next_report = None
        self._waketime = None
        _current[0] = self
        try:
            import mcu
        except ImportError:
            mcu = None
        if not _wrap_home_wait(getattr(mcu, "MCU_endstop", None),
                               HOMING_TIMEOUT, HOMING_TIMEOUT):
            logging.info("tltg_klipper_health: Klipper's endstop layout is "
                         "not as expected; homing timeouts are not reported")
        if not _watch_late_commands(getattr(mcu, "MCU", None)):
            logging.info("tltg_klipper_health: Klipper's MCU commands are not "
                         "as expected; late commands are not reported")
        if not _wrap_trsync(getattr(mcu, "MCU_trsync", None)):
            logging.info("tltg_klipper_health: Klipper's endstop sync is not "
                         "as expected; failed syncs do not report their "
                         "status reports")
        self.printer.register_event_handler("klippy:connect", self._connect)
        self.printer.register_event_handler("klippy:ready", self._ready)

    def _connect(self):
        air = sys.modules.get("extras.air")
        if air is not None and not _wrap_home_wait(
                getattr(air, "WeighEndstopWrapper", None),
                PROBE_SYNC_ERROR, PROBE_SYNC_FAILURE):
            logging.info("tltg_klipper_health: QIDI's load-cell probe is not "
                         "as expected; its endstop sync failures are not "
                         "reported")
        for name in STATUS_COPIERS:
            obj = self.printer.lookup_object(name, None)
            if obj is not None and not lighten_status_copy(obj):
                logging.info("tltg_klipper_health: %s does not use the copy "
                             "module as expected; its status copy is "
                             "unchanged", name)

    def _ready(self):
        now = self.reactor.monotonic()
        self._next_cleanup = now + CLEANUP_INTERVAL
        self._next_report = now + REPORT_INTERVAL
        self._waketime = now + SAMPLE_INTERVAL
        self.reactor.register_timer(self._sample, self._waketime)

    # ---------------------------------------------------------------- timers
    def timer_count(self):
        return len(getattr(self.reactor, "_timers", None) or ())

    def cleanup(self):
        """Unregister finished QIDI load-cell timers; returns how many."""
        removed = 0
        for timer in finished_timers(self.reactor):
            try:
                self.reactor.unregister_timer(timer)
            except ValueError:
                continue
            removed += 1
        if removed:
            self.removed += removed
            logging.info("tltg_klipper_health: removed %d finished QIDI "
                         "load-cell timers (%d since Klipper started)",
                         removed, self.removed)
        return removed

    # -------------------------------------------------------------- sampling
    def _sample(self, eventtime):
        delay = max(0., eventtime - self._waketime)
        self.samples.append((eventtime, time.thread_time(), delay))
        if eventtime >= self._next_cleanup:
            self._next_cleanup = eventtime + CLEANUP_INTERVAL
            self.cleanup()
        if eventtime >= self._next_report:
            self._next_report = eventtime + REPORT_INTERVAL
            self._report(eventtime)
        self._waketime = eventtime + SAMPLE_INTERVAL
        return self._waketime

    def _window(self, eventtime, seconds):
        """Main-thread load, its peak over one sample, and the largest timer
        delay over the last `seconds`."""
        recent = [s for s in self.samples if s[0] >= eventtime - seconds]
        if len(recent) < 2:
            return None, None, None
        load = ((recent[-1][1] - recent[0][1])
                / max(recent[-1][0] - recent[0][0], 1e-6))
        peak = max((b[1] - a[1]) / max(b[0] - a[0], 1e-6)
                   for a, b in zip(recent, recent[1:]))
        return load, peak, max(s[2] for s in recent[1:])

    def _report(self, eventtime):
        timers = self.timer_count()
        if self.timer_baseline is None:
            self.timer_baseline = timers
        load, peak, delay = self._window(eventtime, REPORT_INTERVAL)
        if load is not None:
            logging.info("tltg_klipper_health: timers=%d removed=%d "
                         "main_thread_load=%.2f peak=%.2f max_delay=%.3f",
                         timers, self.removed, load, peak, delay)
        if timers >= self.timer_baseline + TIMER_GROWTH_WARNING:
            self._warn(eventtime, "timers",
                       "Klipper has %d timers, %d more than after it started, "
                       "most of them %s. Klipper slows down as they pile up; "
                       "restart Klipper when the printer is idle, and please "
                       "report this with klippy.log."
                       % (timers, timers - self.timer_baseline,
                          self._top_callbacks()))
        busy, _peak, _delay = self._window(eventtime, BUSY_WINDOW)
        if busy is not None and busy >= BUSY_LOAD \
                and self.samples[0][0] <= eventtime - BUSY_WINDOW + 2.:
            self._warn(eventtime, "busy",
                       "Klipper's main loop has been %d%% busy for %d minutes."
                       " With that little headroom, Box motor moves can fail "
                       "with \"%s\"."
                       % (round(busy * 100), BUSY_WINDOW // 60,
                          HOMING_TIMEOUT))

    def _top_callbacks(self):
        counts = collections.Counter(
            getattr(getattr(t, "callback", None), "__qualname__", "?")
            for t in getattr(self.reactor, "_timers", None) or ())
        return ", ".join("%s (%d)" % item for item in counts.most_common(2))

    def _warn(self, eventtime, kind, message):
        last = self.last_warning.get(kind)
        if last is not None and eventtime - last < WARNING_REPEAT:
            return
        self.last_warning[kind] = eventtime
        logging.warning("tltg_klipper_health: %s", message)
        self.gcode.respond_info(message)

    # ------------------------------------------------------- homing timeouts
    def note_homing_timeout(self, failure, trsyncs):
        eventtime = self.reactor.monotonic()
        mcus = [name for name, _trsync in trsyncs]
        summary, detail = _sync_detail(trsyncs)
        load, peak, delay = self._window(eventtime, TIMEOUT_CONTEXT)
        if load is None:
            context = "no load figures yet"
        else:
            context = ("Klipper's main thread was %d%% busy (peak %d%%) and "
                       "its timers ran up to %d ms late"
                       % (round(load * 100), round(peak * 100),
                          round(delay * 1000)))
        message = ("%s on %s.%s In the %d s before it, %s, with %d timers."
                   % (failure, " and ".join(mcus) or "an endstop", summary,
                      TIMEOUT_CONTEXT, context, self.timer_count()))
        logging.warning("tltg_klipper_health: %s", message)
        if detail:
            logging.info("tltg_klipper_health: %s", detail)
        self.gcode.respond_info(message)

    # --------------------------------------------------------- late commands
    def note_late_command(self, mcu_name, command, ahead, frame):
        """Log a command sent with its clock past, or nearly, by `ahead`
        seconds, and the Python calls that sent it from frame."""
        eventtime = self.reactor.monotonic()
        key = (mcu_name, command)
        last, skipped = self.late_commands.get(key, (None, 0))
        if last is not None and eventtime - last < LATE_COMMAND_REPEAT:
            self.late_commands[key] = (last, skipped + 1)
            return
        self.late_commands[key] = (eventtime, 0)
        calls = traceback.StackSummary.extract(
            traceback.walk_stack(frame), limit=LATE_COMMAND_STACK,
            lookup_lines=False)
        if ahead < 0.:
            timing = "%.1f ms late" % (-ahead * 1000.,)
        else:
            timing = "only %.1f ms ahead" % (ahead * 1000.,)
        logging.warning(
            "tltg_klipper_health: late MCU command: %s on '%s' %s when sent"
            "%s; called from %s", command, mcu_name, timing,
            " (%d more since the last report)" % (skipped,) if skipped else "",
            " < ".join("%s:%d %s" % (os.path.basename(call.filename),
                                     call.lineno, call.name)
                       for call in calls) or "unknown")

    def get_status(self, eventtime=None):
        """Live figures for Fluidd's System Utilization charts: the timer
        count, and the main thread's load and timer delay over the last
        sample."""
        load = delay = None
        if len(self.samples) >= 2:
            (t0, cpu0, _), (t1, cpu1, delay) = self.samples[-2], self.samples[-1]
            load = round((cpu1 - cpu0) / max(t1 - t0, 1e-6), 3)
            delay = round(delay, 3)
        return {
            "timers": self.timer_count(),
            "removed_timers": self.removed,
            "main_thread_load": load,
            "timer_delay": delay,
        }


def load_config(config):
    return KlipperHealth(config)
