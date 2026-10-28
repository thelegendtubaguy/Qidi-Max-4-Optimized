# tltg-optimized:remote-screen-server
"""Serve the QIDI touchscreen to Fluidd's Printer screen card.

Installed by QIDI Max 4 Optimized as /usr/local/lib/tltg_remote_screen.py and run by
tltg-remote-screen.service. nginx routes Fluidd's /tltg-screen/ here only after Moonraker
authorizes the client. The framebuffer is read only while a viewer is connected, and a
JPEG is sent only when the screen changes. Touches are written to the touchscreen's
evdev node, which qidiclient reads as real presses.
"""

from __future__ import annotations

import asyncio
import base64
import fcntl
import hashlib
import io
import json
import mmap
import os
import signal
import struct
import time
import urllib.parse
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:  # Reported to viewers instead of crash-looping the unit.
    Image = None
    IMAGE_ERROR = f"Pillow is unavailable: {exc}"
else:
    IMAGE_ERROR = None

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 7130
FRAMEBUFFER = "/dev/fb0"
POLL_INTERVAL = 0.1
MIN_FRAME_INTERVAL = 0.12
# Each poll compares every SAMPLE_STEP-th row, starting one row later each time.
SAMPLE_STEP = 8
JPEG_QUALITY = 80
MAX_VIEWERS = 4
PING_INTERVAL = 15.0
HEADER_LIMIT = 16384
MAX_MESSAGE = 4096
# qidiclient reads queued touch events in batches and acts on the final state, so a press released in the same
# batch is lost. Presses last at least MIN_PRESS and start at least MIN_GAP after the previous release.
MIN_PRESS = 0.08
MIN_GAP = 0.05
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0x1, 0x2, 0x8, 0x9, 0xA

FBIOGET_VSCREENINFO = 0x4600
EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
SYN_REPORT = 0
BTN_TOUCH = 0x14A
ABS_X, ABS_Y = 0x00, 0x01
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 0x2F, 0x35, 0x36, 0x39
INPUT_PROP_DIRECT = 0x01
INPUT_EVENT = struct.Struct("llHHi")


def log(message: str) -> None:
    print(message, flush=True)


class Unavailable(Exception):
    pass


class ProtocolError(Exception):
    pass


class Framebuffer:
    def __init__(self, path: str = FRAMEBUFFER):
        try:
            self.fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
        except OSError as exc:
            raise Unavailable(f"cannot open {path}: {exc.strerror}") from exc
        try:
            info = self._var_info()
            self.width, self.height = info[0], info[1]
            virtual_height, bpp = info[3], info[6]
            offsets = (info[8], info[11], info[14])
            if bpp != 32 or offsets not in ((16, 8, 0), (0, 8, 16)):
                raise Unavailable(f"unsupported pixel format: {bpp} bpp, RGB offsets {offsets}")
            self.mode = "BGRX" if offsets == (16, 8, 0) else "RGBX"
            self.row_bytes = self.width * 4
            try:
                self.stride = int(Path(f"/sys/class/graphics/{Path(path).name}/stride").read_text())
            except (OSError, ValueError):
                self.stride = self.row_bytes
            self.map = mmap.mmap(self.fd, self.stride * virtual_height, mmap.MAP_SHARED, mmap.PROT_READ)
        except BaseException:
            os.close(self.fd)
            raise
        self.start = 0

    def _var_info(self) -> tuple[int, ...]:
        try:
            return struct.unpack_from("17I", fcntl.ioctl(self.fd, FBIOGET_VSCREENINFO, bytes(160)))
        except OSError as exc:
            raise Unavailable(f"cannot read framebuffer geometry: {exc.strerror}") from exc

    def capture(self) -> bytes:
        info = self._var_info()
        self.start = info[5] * self.stride + info[4] * 4
        return self.map[self.start:self.start + self.stride * self.height]

    def differs(self, frame: bytes, phase: int) -> bool:
        for y in range(phase, self.height, SAMPLE_STEP):
            offset = y * self.stride
            if self.map[self.start + offset:self.start + offset + self.row_bytes] != frame[offset:offset + self.row_bytes]:
                return True
        return False

    def encode(self, frame: bytes) -> bytes:
        image = Image.frombuffer("RGB", (self.width, self.height), frame, "raw", self.mode, self.stride, 1)
        out = io.BytesIO()
        image.save(out, "JPEG", quality=JPEG_QUALITY)
        return out.getvalue()

    def close(self) -> None:
        self.map.close()
        os.close(self.fd)


def _bitmask(text: str) -> int:
    word_bits = struct.calcsize("l") * 8
    value = 0
    for word in text.split():
        value = (value << word_bits) | int(word, 16)
    return value


def find_touchscreen() -> Path:
    for node in sorted(Path("/sys/class/input").glob("event*")):
        try:
            props = _bitmask((node / "device/properties").read_text())
            axes = _bitmask((node / "device/capabilities/abs").read_text())
        except (OSError, ValueError):
            continue
        if props & (1 << INPUT_PROP_DIRECT) and axes & (1 << ABS_MT_POSITION_X) and axes & (1 << ABS_MT_POSITION_Y):
            return Path("/dev/input") / node.name
    raise Unavailable("no touchscreen input device found")


class Touchscreen:
    def __init__(self, width: int, height: int):
        path = find_touchscreen()
        try:
            self.fd = os.open(path, os.O_WRONLY | os.O_CLOEXEC)
        except OSError as exc:
            raise Unavailable(f"cannot open {path}: {exc.strerror}") from exc
        try:
            self.scale_x = self._axis(ABS_MT_POSITION_X, width)
            self.scale_y = self._axis(ABS_MT_POSITION_Y, height)
        except BaseException:
            os.close(self.fd)
            raise
        self.tracking_id = 0
        self.owner = None
        self.pressed_at = 0.0
        self.released_at = 0.0

    def _axis(self, code: int, size: int):
        try:
            _, low, high, _, _, _ = struct.unpack("6i", fcntl.ioctl(self.fd, 0x80184540 + code, bytes(24)))
        except OSError as exc:
            raise Unavailable(f"cannot read touchscreen axes: {exc.strerror}") from exc
        return lambda value: low + round(min(max(value, 0), size - 1) * (high - low) / max(size - 1, 1))

    def _emit(self, *events: tuple[int, int, int]) -> None:
        data = b"".join(INPUT_EVENT.pack(0, 0, kind, code, value) for kind, code, value in events)
        os.write(self.fd, data + INPUT_EVENT.pack(0, 0, EV_SYN, SYN_REPORT, 0))

    def press(self, owner, x: int, y: int) -> None:
        if self.owner is not None:
            return
        self.owner = owner
        self.pressed_at = time.monotonic()
        self.tracking_id = (self.tracking_id + 1) % 0xFFFF
        x, y = self.scale_x(x), self.scale_y(y)
        self._emit(
            (EV_ABS, ABS_MT_SLOT, 0),
            (EV_ABS, ABS_MT_TRACKING_ID, self.tracking_id),
            (EV_ABS, ABS_MT_POSITION_X, x),
            (EV_ABS, ABS_MT_POSITION_Y, y),
            (EV_KEY, BTN_TOUCH, 1),
            (EV_ABS, ABS_X, x),
            (EV_ABS, ABS_Y, y),
        )

    def move(self, owner, x: int, y: int) -> None:
        if self.owner is not owner:
            return
        x, y = self.scale_x(x), self.scale_y(y)
        self._emit(
            (EV_ABS, ABS_MT_SLOT, 0),
            (EV_ABS, ABS_MT_POSITION_X, x),
            (EV_ABS, ABS_MT_POSITION_Y, y),
            (EV_ABS, ABS_X, x),
            (EV_ABS, ABS_Y, y),
        )

    def release(self, owner) -> None:
        if self.owner is not owner:
            return
        self.owner = None
        self.released_at = time.monotonic()
        self._emit(
            (EV_ABS, ABS_MT_SLOT, 0),
            (EV_ABS, ABS_MT_TRACKING_ID, -1),
            (EV_KEY, BTN_TOUCH, 0),
        )


def _frame_header(opcode: int, length: int) -> bytes:
    if length < 126:
        return struct.pack("!BB", 0x80 | opcode, length)
    if length < 1 << 16:
        return struct.pack("!BBH", 0x80 | opcode, 126, length)
    return struct.pack("!BBQ", 0x80 | opcode, 127, length)


class Viewer:
    def __init__(self, server: "ScreenServer", reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.lock = asyncio.Lock()
        self.frame: bytes | None = None
        self.ready = asyncio.Event()

    def offer(self, frame: bytes) -> None:
        # A slow viewer skips to the newest frame instead of queueing old ones.
        self.frame = frame
        self.ready.set()

    async def send(self, opcode: int, payload: bytes) -> None:
        async with self.lock:
            self.writer.write(_frame_header(opcode, len(payload)) + payload)
            await self.writer.drain()

    async def send_json(self, message: dict) -> None:
        await self.send(OP_TEXT, json.dumps(message, separators=(",", ":")).encode("utf-8"))

    async def close(self, code: int, reason: str = "") -> None:
        try:
            await self.send(OP_CLOSE, struct.pack("!H", code) + reason.encode("utf-8")[:120])
        except (ConnectionError, RuntimeError):
            pass

    async def send_loop(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self.ready.wait(), PING_INTERVAL)
            except asyncio.TimeoutError:
                await self.send(OP_PING, b"")
                continue
            self.ready.clear()
            frame, self.frame = self.frame, None
            if frame is not None:
                await self.send(OP_BINARY, frame)

    async def read_message(self) -> tuple[int, bytes]:
        head = await self.reader.readexactly(2)
        opcode, length = head[0] & 0x0F, head[1] & 0x7F
        if not head[0] & 0x80 or not head[1] & 0x80 or head[0] & 0x70:
            raise ProtocolError("unsupported frame")
        if length == 126:
            length = struct.unpack("!H", await self.reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", await self.reader.readexactly(8))[0]
        if length > MAX_MESSAGE:
            raise ProtocolError("message too large")
        mask = await self.reader.readexactly(4)
        payload = await self.reader.readexactly(length)
        return opcode, bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))

    async def handle_touch(self, message: dict) -> None:
        touch = self.server.touch
        action, x, y = message.get("action"), message.get("x"), message.get("y")
        if touch is None:
            return
        if action == "up":
            if touch.owner is self:
                await asyncio.sleep(max(0.0, touch.pressed_at + MIN_PRESS - time.monotonic()))
                touch.release(self)
            return
        if not isinstance(x, int) or not isinstance(y, int) or isinstance(x, bool) or isinstance(y, bool):
            return
        if action == "down":
            await asyncio.sleep(max(0.0, touch.released_at + MIN_GAP - time.monotonic()))
            touch.press(self, x, y)
        elif action == "move":
            touch.move(self, x, y)

    async def receive_loop(self) -> None:
        while True:
            opcode, payload = await self.read_message()
            if opcode == OP_CLOSE:
                await self.close(1000)
                return
            if opcode == OP_PING:
                await self.send(OP_PONG, payload)
            elif opcode == OP_TEXT:
                try:
                    message = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    raise ProtocolError("invalid message") from None
                if isinstance(message, dict) and message.get("type") == "touch":
                    await self.handle_touch(message)


class ScreenServer:
    def __init__(self):
        self.viewers: set[Viewer] = set()
        self.framebuffer: Framebuffer | None = None
        self.touch: Touchscreen | None = None
        self.touch_error: str | None = None
        self.latest: bytes | None = None
        self.capture_task: asyncio.Task | None = None

    def _open_devices(self) -> None:
        if IMAGE_ERROR:
            raise Unavailable(IMAGE_ERROR)
        if self.framebuffer is None:
            self.framebuffer = Framebuffer()
        if self.touch is None:
            try:
                self.touch = Touchscreen(self.framebuffer.width, self.framebuffer.height)
                self.touch_error = None
            except Unavailable as exc:
                self.touch_error = str(exc)

    def _close_devices(self) -> None:
        if self.framebuffer is not None:
            self.framebuffer.close()
            self.framebuffer = None
        if self.touch is not None:
            os.close(self.touch.fd)
            self.touch = None
        self.latest = None

    async def _capture(self) -> None:
        loop = asyncio.get_running_loop()
        framebuffer = self.framebuffer
        last: bytes | None = None
        phase = 0
        sent_at = 0.0
        try:
            while self.viewers:
                changed = last is None or framebuffer.differs(last, phase)
                phase = (phase + 1) % SAMPLE_STEP
                if changed:
                    delay = MIN_FRAME_INTERVAL - (time.monotonic() - sent_at)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    frame = await loop.run_in_executor(None, framebuffer.capture)
                    if frame != last:
                        jpeg = await loop.run_in_executor(None, framebuffer.encode, frame)
                        last, sent_at, self.latest = frame, time.monotonic(), jpeg
                        for viewer in self.viewers:
                            viewer.offer(jpeg)
                await asyncio.sleep(POLL_INTERVAL)
        except Exception as exc:  # A capture failure ends every session; reconnecting reopens the devices.
            log(f"capture stopped: {exc!r}")
            for viewer in list(self.viewers):
                viewer.writer.close()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle(reader, writer)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError, ProtocolError, ValueError):
            pass
        finally:
            writer.close()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
        lines = head.decode("latin-1").split("\r\n")
        method, target, _ = lines[0].split(" ", 2)
        headers = {}
        for line in lines[1:]:
            name, sep, value = line.partition(":")
            if sep:
                headers[name.strip().lower()] = value.strip()
        if method != "GET" or urllib.parse.urlsplit(target).path != "/ws":
            return await self._reject(writer, 404, "Not Found")
        key = headers.get("sec-websocket-key", "")
        if (
            headers.get("upgrade", "").lower() != "websocket"
            or "upgrade" not in [item.strip() for item in headers.get("connection", "").lower().split(",")]
            or headers.get("sec-websocket-version") != "13"
            or not key
        ):
            return await self._reject(writer, 400, "Bad Request")
        # Browsers always send Origin; refusing other origins keeps unrelated pages from driving the screen.
        origin = headers.get("origin")
        if origin and urllib.parse.urlsplit(origin).netloc.lower() != headers.get("host", "").lower():
            return await self._reject(writer, 403, "Forbidden")
        if len(self.viewers) >= MAX_VIEWERS:
            return await self._reject(writer, 503, "Service Unavailable")
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode("ascii")).digest()).decode("ascii")
        writer.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("ascii")
        )
        viewer = Viewer(self, reader, writer)
        try:
            self._open_devices()
        except Unavailable as exc:
            await viewer.send_json({"type": "error", "message": str(exc)})
            await viewer.close(1011)
            return
        await viewer.send_json({
            "type": "hello",
            "width": self.framebuffer.width,
            "height": self.framebuffer.height,
            "touch": self.touch is not None,
            "touch_error": self.touch_error,
        })
        self.viewers.add(viewer)
        log(f"viewer connected ({len(self.viewers)} watching)")
        if self.latest is not None:
            viewer.offer(self.latest)
        if self.capture_task is None or self.capture_task.done():
            self.capture_task = asyncio.ensure_future(self._capture())
        tasks = {asyncio.ensure_future(viewer.send_loop()), asyncio.ensure_future(viewer.receive_loop())}
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                error = None if task.cancelled() else task.exception()
                if error is not None and not isinstance(error, (asyncio.IncompleteReadError, ConnectionError, ProtocolError)):
                    log(f"viewer error: {error!r}")
        finally:
            for task in tasks:
                task.cancel()
            self._leave(viewer)

    def _leave(self, viewer: Viewer) -> None:
        if self.touch is not None:
            self.touch.release(viewer)
        self.viewers.discard(viewer)
        log(f"viewer disconnected ({len(self.viewers)} watching)")
        if not self.viewers:
            if self.capture_task is not None:
                self.capture_task.cancel()
                self.capture_task = None
            self._close_devices()

    async def _reject(self, writer: asyncio.StreamWriter, status: int, reason: str) -> None:
        writer.write(f"HTTP/1.1 {status} {reason}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode("ascii"))
        await writer.drain()

    async def serve(self) -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, stop.set)
        server = await asyncio.start_server(self.handle, LISTEN_HOST, LISTEN_PORT, limit=HEADER_LIMIT)
        log(f"listening on {LISTEN_HOST}:{LISTEN_PORT}")
        async with server:
            await stop.wait()
        # Never leave the touchscreen pressed when the service stops.
        if self.touch is not None and self.touch.owner is not None:
            self.touch.release(self.touch.owner)


def main() -> None:
    asyncio.run(ScreenServer().serve())


if __name__ == "__main__":
    main()
