# Klipper main-loop health for QIDI Max 4 Optimized.
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
# endstop sync times out, so the next such failure explains itself. Its
# status feeds the timer count and main-thread load to Fluidd's System
# Utilization charts.
#
# Status copies: QIDI's multi_color_controller status, which Moonraker reads
# every second, deep-copies its flattened Box status, a dict of about 440
# strings, numbers, and lists, which takes about half of the status's 11 ms.
# Klipper's macros deep-copy each object's whole status the first time a
# macro reads it, such as 48 ms for printer.configfile, which QIDI's start,
# end, and startup macros read many times. In both modules copy.deepcopy is
# replaced with a plain copy of the same dicts, lists, tuples, and values,
# several times faster; anything else still goes to copy.deepcopy.

import collections
import copy
import logging
import sys
import time
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
# Objects whose modules deep-copy whole statuses: QIDI's Box status, and
# Klipper's macro access to every object's status.
STATUS_COPIERS = ("multi_color_controller", "gcode_macro")

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


def _endstop_mcus(endstop):
    names = []
    dispatch = getattr(endstop, "_dispatch", None)
    for trsync in getattr(dispatch, "_trsyncs", None) or ():
        try:
            names.append(trsync.get_mcu().get_name())
        except Exception:
            pass
    if not names:
        try:
            names.append(endstop.get_mcu().get_name())
        except Exception:
            pass
    return names


def _wrap_home_wait():
    try:
        import mcu
    except ImportError:
        return False
    cls = getattr(mcu, "MCU_endstop", None)
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
            if health is not None and HOMING_TIMEOUT in str(e):
                try:
                    health.note_homing_timeout(_endstop_mcus(endstop))
                except Exception:
                    logging.exception("tltg_klipper_health: homing timeout "
                                      "report failed")
            raise
    home_wait._tltg_klipper_health = True
    cls.home_wait = home_wait
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
        self._next_cleanup = 0.
        self._next_report = None
        self._waketime = None
        _current[0] = self
        if not _wrap_home_wait():
            logging.info("tltg_klipper_health: Klipper's endstop layout is "
                         "not as expected; homing timeouts are not reported")
        self.printer.register_event_handler("klippy:connect", self._connect)
        self.printer.register_event_handler("klippy:ready", self._ready)

    def _connect(self):
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
    def note_homing_timeout(self, mcus):
        eventtime = self.reactor.monotonic()
        load, peak, delay = self._window(eventtime, TIMEOUT_CONTEXT)
        if load is None:
            context = "no load figures yet"
        else:
            context = ("Klipper's main thread was %d%% busy (peak %d%%) and "
                       "its timers ran up to %d ms late"
                       % (round(load * 100), round(peak * 100),
                          round(delay * 1000)))
        message = ("%s on %s. In the %d s before it, %s, with %d timers."
                   % (HOMING_TIMEOUT, " and ".join(mcus) or "an endstop",
                      TIMEOUT_CONTEXT, context, self.timer_count()))
        logging.warning("tltg_klipper_health: %s", message)
        self.gcode.respond_info(message)

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
