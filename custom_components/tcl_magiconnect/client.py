"""Bounded asynchronous MagiConnect sessions; no shell, ADB or cloud."""

from __future__ import annotations

import asyncio
import re
import struct
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit

from .protocol import (
    KEYS,
    MAX_FRAME,
    PORT,
    App,
    DeviceInfo,
    ProtocolError,
    decode,
    field,
    frame,
    parse_apps,
    parse_handshake,
)


class CannotConnect(Exception):
    """The TV connection failed or closed."""


class RequestTimeout(CannotConnect):
    """No matching response before the deadline."""


class MagiConnectClient:
    """Serialize operations and negotiate a fresh session for each operation.

    Connections are short lived, including polling. This avoids idle sessions
    displacing the official phone app. Commands are never replayed after failure.
    """

    def __init__(self, host: str, client_id: str, port: int = PORT, timeout: float = 5):
        self.host = host
        self.client_id = field(client_id, maximum=64)
        self.port = port
        self.timeout = timeout
        self.info: DeviceInfo | None = None
        self.expected_unique_id: str | None = None
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._algorithm = -1
        self._closed = False

    @asynccontextmanager
    async def session(self):
        async with self._lock:
            if self._closed:
                raise CannotConnect("Client unloaded")
            try:
                self._algorithm = -1
                async with asyncio.timeout(self.timeout):
                    self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
                    await self._send(f"159>>Home Assistant>>1>>{self.client_id}>>1")
                    self.info = parse_handshake(await self._receive("159"))
                    if self.expected_unique_id and self.info.unique_id != self.expected_unique_id:
                        raise ProtocolError("A different TV answered at the configured address")
                    self._algorithm = self.info.algorithm
                yield self
            except TimeoutError as err:
                raise RequestTimeout("TV response timed out") from err
            except (OSError, asyncio.IncompleteReadError) as err:
                raise CannotConnect("TV connection failed") from err
            finally:
                writer, self._writer = self._writer, None
                self._reader = None
                if writer:
                    writer.close()
                    with suppress(OSError, TimeoutError):
                        async with asyncio.timeout(1):
                            await writer.wait_closed()

    async def _send(self, message: str) -> None:
        if self._writer is None:
            raise CannotConnect("No active session")
        self._writer.write(frame(message, self._algorithm))
        async with asyncio.timeout(self.timeout):
            await self._writer.drain()

    async def _receive(self, command: str, subcommand: str | None = None) -> str:
        if self._reader is None:
            raise CannotConnect("No active session")
        async with asyncio.timeout(self.timeout):
            # Ignore bounded unsolicited notifications/heartbeats, not arbitrary
            # bytes or a mere open TCP port, when validating the protocol.
            for _ in range(64):
                length = struct.unpack(">I", await self._reader.readexactly(4))[0]
                if not 0 < length < MAX_FRAME:
                    raise ProtocolError("Invalid response length")
                message = decode(await self._reader.readexactly(length), self._algorithm)
                parts = message.split(">>", 2)
                if parts[0] == command and (subcommand is None or parts[1:2] == [subcommand]):
                    return message
            raise ProtocolError("Too many unrelated TV messages")

    async def identify(self) -> DeviceInfo:
        async with self.session():
            assert self.info is not None
            return self.info

    async def send_keys(self, commands: list[str], repeat: int = 1, delay: float = 0.15) -> None:
        if not commands or len(commands) * repeat > 100 or not 1 <= repeat <= 100:
            raise ValueError("Use 1 to 100 key presses per call")
        if not 0 <= delay <= 2:
            raise ValueError("Delay must be between 0 and 2 seconds")
        codes = []
        for command in commands:
            if command.lower() not in KEYS:
                raise ValueError(f"Unknown MagiConnect key: {command}")
            codes.append(KEYS[command.lower()])
        async with self.session():
            for index, code in enumerate(codes * repeat):
                if index:
                    await asyncio.sleep(delay)
                await self._send(f"149>>{code}")

    async def send_text(self, text: str) -> None:
        text = field(text)
        async with self.session():
            await self._send(f"155>>{text}")

    async def move_mouse(self, x: int, y: int) -> None:
        if not all(isinstance(v, int) and -2000 <= v <= 2000 for v in (x, y)):
            raise ValueError("Mouse delta must be an integer from -2000 to 2000")
        async with self.session():
            await self._send(f"151>>{x}>>{y}")

    async def get_apps(self) -> list[App]:
        async with self.session():
            await self._send("223>>GET")
            return parse_apps(await self._receive("223", "GET"))

    async def launch_app(self, package: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package):
            raise ValueError("An Android package identifier is required")
        async with self.session():
            await self._send(f"223>>OPEN>>{package}")

    async def get_screenshot_url(self) -> str:
        async with self.session():
            await self._send("225>>")
            parts = (await self._receive("225")).split(">>")
            if len(parts) < 3 or parts[1] != "0":
                raise ProtocolError("TV refused the screenshot")
            url = urlsplit(parts[2])
            # Return only a URL on the configured TV, never follow redirects or
            # fetch a URL supplied by a device on behalf of Home Assistant.
            if url.scheme not in {"http", "https"} or url.hostname != self.host or url.username:
                raise ProtocolError("Unexpected screenshot URL")
            return parts[2]

    async def player_command(self, action: str) -> None:
        commands = {"play": "134>>", "pause": "135>>", "stop": "129>>"}
        if action not in commands:
            raise ValueError("Unknown native player action")
        async with self.session():
            await self._send(commands[action])

    async def cast_video(self, url: str, title: str = "Home Assistant") -> None:
        field(url)
        field(title, maximum=256)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
            raise ValueError("Video must be an HTTP(S) URL accessible to the TV")
        if "->" in url or "->" in title:
            raise ValueError("Video fields cannot contain ->")
        async with self.session():
            await self._send("129>>")
            await self._send("133>>Video")
            # VideoInfo.getInfo(): url,title,player,album,cover,portrait,width,height.
            await self._send(f"134>>{url}->{title}->null->null->null->false->null->null")

    async def close(self) -> None:
        self._closed = True
        if self._writer:
            self._writer.close()
        async with self._lock:
            pass
