# QIDI RS-485 device monitor for QIDI Max 4 Optimized.
#
# Firmware 01.01.07.01 loads QIDI's RS-485 stack (`[box485]`, `[box2base]`) for
# Boxes, buffers, and filament racks that connect through a USB-to-RS-485
# adapter instead of running Klipper over USB. This project has not seen that
# hardware, so this module detects it and records what it does:
#
# - Detection: box485 opening its port, RS-485 devices registering, RS-485 Box
#   ids in saved variables, USB serial adapters that are not Klipper MCUs, and
#   a multi_color_controller Box identity other than the USB Box's.
# - Once detected: every frame box485 sends and receives, QIDI's RS-485 log
#   lines, and status changes go to printer_data/logs/tltg_box485.log, and a
#   shareable summary to tltg_box485_report.json. Device chip ids and adapter
#   serial numbers are replaced with salted hashes in both.
#
# Without RS-485 hardware it writes nothing. It also:
# - keeps box485 from opening a Klipper MCU's serial port. box485 polls its
#   port for reads, so pointed at a Box's Klipper port it takes that MCU's
#   replies and the Box drops;
# - lets QIDI's "Can not find 485 device", logged every 2 s while no adapter
#   is attached, into klippy.log once an hour with a repeat count.

import hashlib
import json
import logging
import os
import re
import subprocess
import threading
import time

OUTPUT_NAME = "tltg_box485.log"
ROTATED_NAME = "tltg_box485.log.1"
REPORT_NAME = "tltg_box485_report.json"
SALT_NAME = ".tltg_box485_salt"
FIRMWARE_MANIFEST = "/home/qidi/update/firmware_manifest.json"
ISSUES_URL = "https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/issues"

SPAM_MESSAGE = "Can not find 485 device"
SPAM_SUMMARY_INTERVAL = 3600.0
SAMPLE_INTERVAL = 10.0
REPORT_INTERVAL = 600.0
# Identical frames for one address and command are written once, then again
# with a repeat count when the payload changes or after this many seconds.
FRAME_REPEAT_INTERVAL = 60.0
VENDOR_HISTORY = 200

# QIDI's modules are compiled with Cython, so a log record names the Python
# code that called into them, not the module that logged. RS-485 lines are
# recognized by their markers instead; Box lines in general only once RS-485
# is detected, since USB Boxes log them too.
RS485_LINE = re.compile(
    r"(?<![\d.])485(?!\d)|\u3010(\u901a\u4fe1|send_wait_respond|Hall)"
    r"|\u6362\u6599\u67b6|\u7f13\u51b2\u5668|_ACK\b|STATUS_REPORT|UUID"
    r"|uuid|[Rr]ack|[Bb]uffer")
BOX_LINE = re.compile(
    r"(?i)box|slot|T_MANAGER|filament|rfid|dry|\u6599\u76d2|\u8fdb\u6599"
    r"|\u9000\u6599")
IGNORED_LINES = ("Stats ", "tltg_box485_monitor", SPAM_MESSAGE)
VENDOR_FILES = ("box485.py", "box485_multicolor.so", "box485_buffer.so",
                "box485_rack.so", "box_protocol.so", "box2base.so",
                "multi_color_controller.so")

# Frame: AA 55, address, command, payload length, payload, CRC-16/ARC of
# everything before it, big-endian.
FRAME_HEADER = b"\xaa\x55"
FRAME_OVERHEAD = 7
MAX_PENDING = 4096
UUID_ACK = 2
CHIP_ID_BYTES = 12
SAVED_ID_VARIABLE = re.compile(r"^box\d+_mcu_id$")
SAVED_RS485_VARIABLES = ("box485_leases",)
HEX_ID = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{24}(?![0-9A-Fa-f])")
BY_ID_SERIAL = re.compile(r"^(usb-.+_)([0-9A-Za-z]{8,})(-if\d+.*)$")
USB_TTY = re.compile(r"^tty(USB|ACM)\d+$")
USB_ATTRIBUTES = ("idVendor", "idProduct", "manufacturer", "product",
                  "bcdDevice", "speed")
DMESG_WORDS = ("ch341", "ch343", "cp210", "ftdi", "pl2303", "ttyusb",
               "usb-serial", "usbserial")


def _crc16_arc(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonable(value, depth=0):
    if depth > 6:
        return repr(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item, depth + 1)
                for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item, depth + 1) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return {"type": type(value).__name__,
                "attributes": {key: _jsonable(item, depth + 1)
                               for key, item in attributes.items()
                               if not key.startswith("_")
                               and not callable(item)
                               and key not in ("printer", "reactor", "gcode",
                                               "manager")}}
    return repr(value)


class Redactor:
    """Replaces device chip ids and adapter serial numbers with hashes that
    stay the same on this printer but cannot be reversed without its salt."""

    def __init__(self, salt_path):
        self.salt_path = salt_path
        self._salt = None
        self._ids = {}

    def _salt_bytes(self):
        if self._salt is None:
            try:
                with open(self.salt_path, "r", encoding="utf-8") as handle:
                    self._salt = bytes.fromhex(handle.read().strip())
            except (OSError, ValueError):
                self._salt = os.urandom(16)
                try:
                    fd = os.open(self.salt_path,
                                 os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        handle.write(self._salt.hex() + "\n")
                except OSError:
                    pass
        return self._salt

    def label(self, raw):
        digest = hashlib.sha256(self._salt_bytes() + raw.lower().encode())
        return "<id:%s>" % digest.hexdigest()[:10]

    def add(self, raw):
        if isinstance(raw, (bytes, bytearray)):
            raw = bytes(raw).hex()
        raw = str(raw).strip().strip("'\"").lower()
        if len(raw) >= 8 and raw not in self._ids:
            self._ids[raw] = self.label(raw)

    def text(self, value):
        value = str(value)
        for raw, label in self._ids.items():
            value = re.sub(re.escape(raw), label, value, flags=re.IGNORECASE)
        return HEX_ID.sub(lambda match: self.label(match.group(0)), value)

    def device_name(self, name):
        match = BY_ID_SERIAL.match(name)
        if not match:
            return self.text(name)
        return match.group(1) + self.label(match.group(2)) + match.group(3)

    def path(self, path):
        if not path:
            return path
        head, name = os.path.split(str(path))
        return os.path.join(head, self.device_name(name))


class FrameDecoder:
    def __init__(self):
        self.pending = bytearray()

    def feed(self, data):
        """Returns (frames, junk): frames as (address, command, payload,
        crc_ok); junk as byte strings that are not part of a frame."""
        self.pending += data
        frames = []
        junk = []
        while True:
            start = self.pending.find(FRAME_HEADER)
            if start < 0:
                keep = 1 if self.pending.endswith(FRAME_HEADER[:1]) else 0
                cut = len(self.pending) - keep
                if cut:
                    junk.append(bytes(self.pending[:cut]))
                    del self.pending[:cut]
                break
            if start:
                junk.append(bytes(self.pending[:start]))
                del self.pending[:start]
            if len(self.pending) < 5:
                break
            total = FRAME_OVERHEAD + self.pending[4]
            if len(self.pending) < total:
                if len(self.pending) > MAX_PENDING:
                    junk.append(bytes(self.pending))
                    del self.pending[:]
                break
            frame = bytes(self.pending[:total])
            crc_ok = (_crc16_arc(frame[:-2])
                      == int.from_bytes(frame[-2:], "big"))
            if not crc_ok:
                # Resynchronize on the next header rather than trusting the
                # length byte of a damaged frame.
                junk.append(frame[:2])
                del self.pending[:2]
                frames.append((frame[2], frame[3], frame[5:-2], False))
                continue
            frames.append((frame[2], frame[3], frame[5:-2], True))
            del self.pending[:total]
        return frames, junk


class SerialTap:
    """Delegates to box485's pyserial port and reports the bytes it moves."""

    def __init__(self, serial_port, sink):
        object.__setattr__(self, "_tltg_serial", serial_port)
        object.__setattr__(self, "_tltg_sink", sink)

    def _tltg_report(self, direction, data):
        if data:
            try:
                self._tltg_sink.on_bytes(direction, bytes(data))
            except Exception:
                logging.exception("tltg_box485_monitor: frame capture failed")

    def read(self, *args, **kwargs):
        data = self._tltg_serial.read(*args, **kwargs)
        self._tltg_report("rx", data)
        return data

    def read_all(self, *args, **kwargs):
        data = self._tltg_serial.read_all(*args, **kwargs)
        self._tltg_report("rx", data)
        return data

    def read_until(self, *args, **kwargs):
        data = self._tltg_serial.read_until(*args, **kwargs)
        self._tltg_report("rx", data)
        return data

    def readline(self, *args, **kwargs):
        data = self._tltg_serial.readline(*args, **kwargs)
        self._tltg_report("rx", data)
        return data

    def write(self, data, *args, **kwargs):
        result = self._tltg_serial.write(data, *args, **kwargs)
        self._tltg_report("tx", data)
        return result

    def __getattr__(self, name):
        return getattr(self._tltg_serial, name)

    def __setattr__(self, name, value):
        setattr(self._tltg_serial, name, value)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self._tltg_serial.__exit__(*args)


class RepeatSummaryFilter(logging.Filter):
    """Lets QIDI's no-adapter line through once an hour with a count."""

    def __init__(self):
        logging.Filter.__init__(self)
        self.suppressed = 0
        self.last_passed = None

    def filter(self, record):
        if record.msg != SPAM_MESSAGE or record.args:
            return True
        now = time.time()
        if (self.last_passed is not None
                and now - self.last_passed < SPAM_SUMMARY_INTERVAL):
            self.suppressed += 1
            return False
        if self.suppressed:
            record.msg = ("%s (repeated %d times since %s; tltg_box485_monitor"
                          " logs it hourly)" % (
                              SPAM_MESSAGE, self.suppressed,
                              time.strftime("%H:%M:%S",
                                            time.localtime(self.last_passed))))
        self.suppressed = 0
        self.last_passed = now
        return True


class VendorLogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._busy = threading.local()

    def emit(self, record):
        monitor = _STATE["monitor"]
        if monitor is None or getattr(self._busy, "value", False):
            return
        self._busy.value = True
        try:
            monitor.on_vendor_record(record)
        finally:
            self._busy.value = False


# Klipper's RESTART builds new printer objects in the same process, so the
# class patch, logging filter, and handler are installed once and always
# report to the latest monitor.
_STATE = {"monitor": None, "filter": None, "handler": None}
PATCH_MARKER = "_tltg_box485_monitor"


def _patch_manager(cls):
    if getattr(cls, PATCH_MARKER, None):
        return getattr(cls, PATCH_MARKER)
    original_connect = getattr(cls, "connect", None)
    original_reconnect = getattr(cls, "_on_reconnect_timer", None)
    if not callable(original_connect) or not callable(original_reconnect):
        return None

    def connect(self, *args, **kwargs):
        monitor = _STATE["monitor"]
        if monitor is not None and monitor.refuse_port(self):
            return None
        try:
            return original_connect(self, *args, **kwargs)
        finally:
            if monitor is not None:
                monitor.tap(self)

    def _on_reconnect_timer(self, eventtime, *args, **kwargs):
        monitor = _STATE["monitor"]
        if monitor is not None and monitor.refuse_port(self):
            return self.reactor.NEVER
        try:
            return original_reconnect(self, eventtime, *args, **kwargs)
        finally:
            if monitor is not None:
                monitor.tap(self)

    cls.connect = connect
    cls._on_reconnect_timer = _on_reconnect_timer
    setattr(cls, PATCH_MARKER, original_connect)
    return original_connect


class Box485Monitor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.max_log_bytes = config.getint(
            "max_log_bytes", 4 * 1024 * 1024, minval=256 * 1024)
        self.log_dir = self._log_dir()
        self.path = os.path.join(self.log_dir, OUTPUT_NAME)
        self.report_path = os.path.join(self.log_dir, REPORT_NAME)
        self.redactor = Redactor(os.path.join(
            os.path.dirname(self.log_dir), SALT_NAME))
        self.extras_dir = os.path.dirname(os.path.abspath(__file__))
        self.mcu_serials = []
        for section in config.get_prefix_sections("mcu"):
            name = section.get_name()
            if name != "mcu" and not name.startswith("mcu "):
                continue
            serial_port = section.get("serial", None)
            if serial_port:
                self.mcu_serials.append((name, serial_port))
        self.has_box485 = config.has_section("box485")
        self.patch = None
        self.patch_error = None
        self._lock = threading.Lock()
        self._handle = None
        self._active = False
        self._signals = {}
        self._conflict = None
        self._conflict_reported = False
        self._notified = False
        self._decoders = {"rx": FrameDecoder(), "tx": FrameDecoder()}
        self._frame_counts = {}
        self._last_frames = {}
        self._byte_counts = {"rx": 0, "tx": 0}
        self._crc_errors = {"rx": 0, "tx": 0}
        self._junk_bytes = {"rx": 0, "tx": 0}
        self._vendor_history = []
        self._last_status = {}
        self._last_report = 0.0
        self._names = self._command_names()
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "TLTG_RS_BOX_REPORT", self.cmd_TLTG_RS_BOX_REPORT,
            desc="Write the QIDI RS-485 device report")
        _STATE["monitor"] = self
        self._install_logging()
        if self.has_box485:
            self._install_patch()
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.printer.register_event_handler("klippy:shutdown",
                                            self._handle_shutdown)
        self.printer.register_event_handler("klippy:disconnect",
                                            self._handle_disconnect)

    # --------------------------------------------------------------- set up
    def _log_dir(self):
        log_file = self.printer.get_start_args().get("log_file")
        if log_file:
            return os.path.dirname(os.path.abspath(log_file))
        return os.getcwd()

    def _install_logging(self):
        root = logging.getLogger()
        if _STATE["filter"] is None:
            _STATE["filter"] = RepeatSummaryFilter()
            root.addFilter(_STATE["filter"])
        if _STATE["handler"] is None:
            _STATE["handler"] = VendorLogHandler()
            root.addHandler(_STATE["handler"])

    def _install_patch(self):
        try:
            from . import box485_multicolor
            cls = box485_multicolor.Box485Manager
        except Exception as exc:
            self.patch_error = "box485_multicolor unavailable: %s" % exc
            logging.warning("tltg_box485_monitor: %s", self.patch_error)
            return
        original_connect = _patch_manager(cls)
        if original_connect is None:
            self.patch_error = ("Box485Manager has no connect or"
                                " _on_reconnect_timer")
            logging.warning("tltg_box485_monitor: %s; port guard and frame"
                            " capture are off", self.patch_error)
            return
        self.patch = cls
        # A [box485] section loaded before this one bound the original
        # connect as its klippy:ready handler.
        handlers = getattr(self.printer, "event_handlers", {})
        ready = handlers.get("klippy:ready", [])
        for index, callback in enumerate(ready):
            owner = getattr(callback, "__self__", None)
            if (isinstance(owner, cls)
                    and getattr(callback, "__func__", None)
                    is original_connect):
                ready[index] = owner.connect

    def _command_names(self):
        try:
            from . import box_protocol
            return {int(key): str(value)
                    for key, value in box_protocol.REV_SLAVE_CMD.items()}
        except Exception:
            return {}

    # ----------------------------------------------------------------- guard
    def _port_owner(self, port):
        name = os.path.basename(str(port))
        real = os.path.realpath(str(port))
        for mcu_name, mcu_port in self.mcu_serials:
            if mcu_port == port or os.path.realpath(mcu_port) == real:
                return mcu_name
        if name.startswith("usb-Klipper_"):
            return "a Klipper MCU (%s)" % self.redactor.device_name(name)
        return None

    def refuse_port(self, manager):
        port = getattr(manager, "port", None)
        if not port:
            return False
        owner = self._port_owner(port)
        if owner is None:
            self._conflict = None
            return False
        self._conflict = {"port": self.redactor.path(port), "owner": owner}
        if not self._conflict_reported:
            self._conflict_reported = True
            logging.warning(
                "tltg_box485_monitor: [box485] serial_port %s is the serial"
                " port of %s; keeping box485 from opening it",
                self.redactor.path(port), owner)
            self._activate("box485 serial_port is a Klipper MCU port")
        return True

    def _conflict_message(self):
        return (
            "!! [box485] serial_port in printer.cfg is the serial port of %s."
            " QIDI's RS-485 code would read that MCU's messages and break its"
            " connection, so it stays closed. Set serial_port back to"
            " /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0. The QIDI Box"
            " ids in box.cfg belong in [mcu mcu_boxN], not [box485]."
            % self._conflict["owner"])

    # ------------------------------------------------------------- capture
    def tap(self, manager):
        serial_port = getattr(manager, "ser", None)
        if serial_port is None or isinstance(serial_port, SerialTap):
            return
        manager.ser = SerialTap(serial_port, self)
        self._activate("box485 opened %s"
                       % self.redactor.path(getattr(manager, "port", "")))

    def on_bytes(self, direction, data):
        self._byte_counts[direction] += len(data)
        frames, junk = self._decoders[direction].feed(data)
        now = self.reactor.monotonic()
        for chunk in junk:
            self._junk_bytes[direction] += len(chunk)
            self._write("%s t=%.3f junk len=%d %s" % (
                direction, now, len(chunk), self.redactor.text(chunk.hex())))
        for address, command, payload, crc_ok in frames:
            self._frame(direction, now, address, command, payload, crc_ok)

    def _frame(self, direction, now, address, command, payload, crc_ok):
        name = self._names.get(command, "cmd%d" % command)
        if not crc_ok:
            self._crc_errors[direction] += 1
        elif (command == UUID_ACK and direction == "rx"
                and len(payload) >= CHIP_ID_BYTES):
            self.redactor.add(payload[:CHIP_ID_BYTES])
        count_key = "%s %s" % (direction, name)
        self._frame_counts[count_key] = self._frame_counts.get(count_key, 0) + 1
        key = (direction, address, command)
        last = self._last_frames.get(key)
        if (crc_ok and last is not None and last[0] == payload
                and now - last[1] < FRAME_REPEAT_INTERVAL):
            last[2] += 1
            return
        repeats = last[2] if last is not None else 0
        self._last_frames[key] = [payload, now, 0]
        self._write("%s t=%.3f addr=%d %s(%d) len=%d %s%s%s" % (
            direction, now, address, name, command, len(payload),
            self.redactor.text(payload.hex()) or "-",
            "" if crc_ok else " crc=bad",
            " (previous frame repeated %d times)" % repeats if repeats else ""))

    def on_vendor_record(self, record):
        if str(record.msg).startswith(IGNORED_LINES):
            return
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        if message.startswith(IGNORED_LINES):
            return
        if not RS485_LINE.search(message) and not (
                self._active and BOX_LINE.search(message)):
            return
        line = "%s %s: %s" % (
            time.strftime("%H:%M:%S", time.localtime(record.created)),
            record.levelname, message)
        if record.exc_info and record.exc_info[1] is not None:
            line += " [%s: %s]" % (type(record.exc_info[1]).__name__,
                                   record.exc_info[1])
        with self._lock:
            self._vendor_history.append(line)
            del self._vendor_history[:-VENDOR_HISTORY]
        if self._active:
            self._write("log %s" % self.redactor.text(line))

    # --------------------------------------------------------------- files
    def _write(self, message, durable=False):
        if not self._active:
            return
        with self._lock:
            try:
                if self._handle is None:
                    self._rotate()
                    self._handle = open(self.path, "a", encoding="utf-8")
                stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                self._handle.write("%s %s\n" % (stamp, message))
                self._handle.flush()
                if durable:
                    os.fsync(self._handle.fileno())
                if self._handle.tell() >= self.max_log_bytes:
                    self._handle.close()
                    self._handle = None
            except Exception:
                logging.exception("tltg_box485_monitor: write failed")
                self._handle = None

    def _rotate(self):
        try:
            if os.path.getsize(self.path) >= self.max_log_bytes:
                os.replace(self.path, os.path.join(self.log_dir, ROTATED_NAME))
        except OSError:
            pass

    def _close(self):
        with self._lock:
            if self._handle is not None:
                try:
                    self._handle.close()
                except Exception:
                    pass
                self._handle = None

    def _write_report(self):
        report = self._report()
        text = self.redactor.text(json.dumps(report, indent=2, sort_keys=True,
                                             default=repr))
        temporary = self.report_path + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
            os.replace(temporary, self.report_path)
        except OSError:
            logging.exception("tltg_box485_monitor: report write failed")
        self._last_report = self.reactor.monotonic()
        return report

    # ------------------------------------------------------------ evidence
    def _manager(self):
        return self.printer.lookup_object("box485", None)

    def _variables(self):
        save_variables = self.printer.lookup_object("save_variables", None)
        if save_variables is None:
            return {}
        try:
            variables = save_variables.get_status(0.0).get("variables")
        except Exception:
            variables = None
        if isinstance(variables, dict):
            return variables
        return getattr(save_variables, "allVariables", {}) or {}

    def _status(self, name):
        obj = self.printer.lookup_object(name, None)
        if obj is None or not hasattr(obj, "get_status"):
            return None
        try:
            return _jsonable(obj.get_status(self.reactor.monotonic()))
        except Exception as exc:
            return {"error": repr(exc)}

    def _serial_nodes(self):
        """Returns (by-id name or None, /dev node, is a Klipper MCU) for every
        USB serial device, with names unredacted."""
        nodes = []
        mcu_paths = set(os.path.realpath(port) for _, port in self.mcu_serials)
        by_id = "/dev/serial/by-id"
        try:
            names = sorted(os.listdir(by_id))
        except OSError:
            names = []
        listed = set()
        for name in names:
            real = os.path.realpath(os.path.join(by_id, name))
            listed.add(os.path.basename(real))
            nodes.append((name, os.path.basename(real),
                          real in mcu_paths or name.startswith("usb-Klipper_")))
        try:
            entries = sorted(os.listdir("/dev"))
        except OSError:
            entries = []
        for node in entries:
            if USB_TTY.match(node) and node not in listed:
                nodes.append((None, node, False))
        return nodes

    def _usb_serial_devices(self):
        devices = []
        for name, node, klipper_mcu in self._serial_nodes():
            device = {"by_id": self.redactor.device_name(name) if name
                      else None, "node": node, "klipper_mcu": klipper_mcu}
            device.update(self._usb_attributes(node))
            devices.append(device)
        return devices

    def _usb_attributes(self, node):
        info = {}
        base = os.path.join("/sys/class/tty", node, "device")
        try:
            info["driver"] = os.path.basename(
                os.path.realpath(os.path.join(base, "driver")))
        except OSError:
            pass
        path = os.path.realpath(base)
        for _ in range(4):
            if os.path.exists(os.path.join(path, "idVendor")):
                for attribute in USB_ATTRIBUTES:
                    try:
                        with open(os.path.join(path, attribute), "r",
                                  encoding="utf-8") as handle:
                            info[attribute] = handle.read().strip()
                    except OSError:
                        pass
                info["usb_path"] = os.path.basename(path)
                break
            path = os.path.dirname(path)
        return info

    def _detect(self):
        signals = {}
        manager = self._manager()
        if manager is not None and self._conflict is None:
            if getattr(manager, "ser", None) is not None:
                signals["port_open"] = self.redactor.path(
                    getattr(manager, "port", ""))
            status = self._status("box485") or {}
            if (status.get("box_count") or status.get("boxes")
                    or status.get("buffer")
                    or getattr(manager, "addr_to_dev", None)
                    or getattr(manager, "unassigned_multicolor_boxes", None)):
                signals["devices"] = True
        if sum(self._byte_counts.values()):
            signals["traffic"] = True
        variables = self._variables()
        saved = sorted(
            key for key, value in variables.items()
            if (SAVED_ID_VARIABLE.match(key)
                or key in SAVED_RS485_VARIABLES)
            and value not in (None, "", "None", {}, []))
        if saved:
            signals["saved_variables"] = saved
        adapters = [self.redactor.device_name(name) if name else node
                    for name, node, klipper_mcu in self._serial_nodes()
                    if not klipper_mcu]
        if adapters:
            signals["usb_serial_adapter"] = adapters
        identity = None
        controller = self.printer.lookup_object("multi_color_controller", None)
        try:
            box = controller.get_status(self.reactor.monotonic()).get("box")
            identity = box.get("identity")
        except Exception:
            pass
        if identity not in (None, "", "box_v1"):
            signals["box_identity"] = identity
        return signals

    def _register_ids(self):
        for key, value in self._variables().items():
            if SAVED_ID_VARIABLE.match(key) and value:
                self.redactor.add(value)
        manager = self._manager()
        rack_uuid = getattr(manager, "rack_uuid", None) if manager else None
        if rack_uuid:
            self.redactor.add(re.sub(r"[^0-9A-Fa-f]", "", str(rack_uuid)))

    def _manager_state(self, manager):
        state = {}
        for name in ("port", "baud", "timeout", "serial_online", "addr_min",
                     "addr_max", "box_list", "slots", "leases",
                     "unassigned_multicolor_boxes", "buffer_addr",
                     "rack_addr", "rack_status", "rack_uuid", "current_channel",
                     "aht20_temp", "aht20_humidity", "ntc0", "ntc1",
                     "server_status", "hello_pending", "extrude_length",
                     "extrude_timeout", "_hall_value", "_detect_pin_enabled"):
            if hasattr(manager, name):
                state[name] = _jsonable(getattr(manager, name))
        state["port"] = self.redactor.path(state.get("port"))
        devices = getattr(manager, "addr_to_dev", None)
        if isinstance(devices, dict):
            state["devices"] = {str(address): _jsonable(device)
                                for address, device in devices.items()}
        state["serial_type"] = type(getattr(manager, "ser", None)).__name__
        return state

    def _firmware_versions(self):
        try:
            with open(FIRMWARE_MANIFEST, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError):
            return None
        if not isinstance(manifest, dict):
            return None
        return {key: (value.get("version") if isinstance(value, dict)
                      else value)
                for key, value in manifest.items()}

    def _vendor_files(self):
        files = {}
        for name in VENDOR_FILES:
            path = os.path.join(self.extras_dir, name)
            try:
                files[name] = _sha256(path)
            except OSError:
                files[name] = None
        return files

    def _dmesg(self):
        try:
            result = subprocess.run(
                ["dmesg"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=3.0)
        except Exception as exc:
            return ["capture failed: %s" % exc]
        lines = result.stdout.decode("utf-8", "replace").splitlines()
        return [line.strip() for line in lines
                if any(word in line.lower() for word in DMESG_WORDS)][-40:]

    def _report(self):
        self._register_ids()
        manager = self._manager()
        variables = self._variables()
        globals_status = self._status("gcode_macro _tltg_optimized_globals")
        objects = sorted(name for name, _ in self.printer.lookup_objects())
        commands = sorted(
            name for name in getattr(self.gcode, "ready_gcode_handlers", {})
            if re.search(r"BOX|485|RACK|BUFFER|HALL|^T_|FILAMENT|UUID|"
                         r"VERSION", name))
        with self._lock:
            vendor_lines = list(self._vendor_history)
        state_message, state = self.printer.get_state_message()
        return {
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "package_version": (globals_status or {}).get("package_version"),
            "firmware": self._firmware_versions(),
            "klippy_state": state,
            "klippy_state_message": state_message,
            "detected": self._active,
            "signals": self._signals,
            "port_conflict": self._conflict,
            "box485_configured": self.has_box485,
            "capture": {
                "patched": self.patch is not None,
                "patch_error": self.patch_error,
                "bytes": dict(self._byte_counts),
                "crc_errors": dict(self._crc_errors),
                "junk_bytes": dict(self._junk_bytes),
                "frames": dict(sorted(self._frame_counts.items())),
            },
            "box485": self._manager_state(manager) if manager else None,
            "box485_status": self._status("box485"),
            "multi_color_controller_status": self._status(
                "multi_color_controller"),
            "saved_variables": {
                key: _jsonable(value) for key, value in variables.items()
                if re.search(r"box|485|slot|rack|buffer|filament|color|vendor",
                             key)},
            "usb_serial_devices": self._usb_serial_devices(),
            "mcu_serials": {name: self.redactor.path(port)
                            for name, port in self.mcu_serials},
            "vendor_files_sha256": self._vendor_files(),
            "printer_objects": objects,
            "box_commands": commands,
            "dmesg_usb_serial": self._dmesg(),
            "recent_rs485_log": vendor_lines,
        }

    # ------------------------------------------------------------- control
    def _activate(self, reason):
        first = not self._active
        self._active = True
        self._register_ids()
        if first:
            self._write("detected: %s; tltg_box485_monitor is recording"
                        % reason, durable=True)
            with self._lock:
                history = list(self._vendor_history)
            for line in history:
                self._write("log (before detection) %s"
                            % self.redactor.text(line))
            self._notify(reason)
        else:
            self._write("signal: %s" % reason)

    def _notify(self, reason):
        if self._notified or self.printer.get_state_message()[1] != "ready":
            return
        self._notified = True
        if self._conflict is not None:
            self.gcode.respond_raw(self._conflict_message())
            return
        if set(self._signals) == set(["usb_serial_adapter"]):
            found = ("A USB serial adapter that isn't a Klipper MCU is"
                     " connected (%s). If it belongs to a QIDI RS-485 Box,"
                     " buffer, or rack, please" % reason)
        else:
            found = ("QIDI RS-485 hardware detected (%s). TLTG Optimized has"
                     " not been tested with RS-485 Boxes, buffers, or racks"
                     " yet, so it is recording what they do. Please" % reason)
        self.gcode.respond_info(
            "%s open an issue at %s and attach tltg_box485_report.json and"
            " tltg_box485.log from Fluidd's logs folder." % (found, ISSUES_URL))

    def _handle_ready(self):
        self.reactor.register_timer(self._sample, self.reactor.NOW)

    def _handle_shutdown(self):
        if self._active:
            self._write("klippy shutdown: %s"
                        % self.printer.get_state_message()[0], durable=True)
            self._write_report()

    def _handle_disconnect(self):
        if self._active:
            self._write_report()
        self._close()

    def _sample(self, eventtime):
        try:
            signals = self._detect()
            if signals != self._signals:
                added = sorted(set(signals) - set(self._signals))
                removed = sorted(set(self._signals) - set(signals))
                self._signals = signals
                if signals:
                    reason = ", ".join(
                        "%s=%s" % (key, signals[key]) for key in sorted(signals))
                    if added or not self._active:
                        self._activate(self.redactor.text(reason))
                    else:
                        self._write("signals: %s"
                                    % self.redactor.text(reason))
                if removed and self._active:
                    self._write("signals gone: %s" % ", ".join(removed))
                if self._active:
                    self._write_report()
            if self._active:
                for name in ("box485", "multi_color_controller"):
                    status = self._status(name)
                    if status != self._last_status.get(name):
                        self._last_status[name] = status
                        self._write("status %s %s" % (
                            name, self.redactor.text(json.dumps(
                                status, sort_keys=True, default=repr))))
                if eventtime - self._last_report >= REPORT_INTERVAL:
                    self._write_report()
        except Exception:
            logging.exception("tltg_box485_monitor: sample failed")
        return eventtime + SAMPLE_INTERVAL

    def cmd_TLTG_RS_BOX_REPORT(self, gcmd):
        self._signals = self._detect()
        self._write_report()
        if self._conflict is not None:
            gcmd.respond_raw(self._conflict_message())
        if self._signals or self._active:
            gcmd.respond_info(
                "RS-485 signals: %s. Report written to %s; recording to %s."
                % (self.redactor.text(", ".join(
                    "%s=%s" % (key, self._signals[key])
                    for key in sorted(self._signals))) or "none now",
                   self.report_path, self.path))
        else:
            gcmd.respond_info(
                "No QIDI RS-485 hardware detected. Report written to %s."
                % self.report_path)

    def get_status(self, eventtime):
        return {"detected": self._active,
                "signals": sorted(self._signals),
                "port_conflict": self._conflict is not None}


def load_config(config):
    return Box485Monitor(config)
