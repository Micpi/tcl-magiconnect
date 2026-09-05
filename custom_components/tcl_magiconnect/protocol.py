"""MagiConnect wire format, independently implemented from APK observations.

See docs/PROTOCOL.md for provenance. No Android or Home Assistant dependency.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PORT = 6553
DISCOVERY_PORT = 6537
MAX_FRAME = 1048576
AES_KEY = b"tnscreentnscreen"
AES_IV = bytes.fromhex("1234567890abcdef1234567890abcdef")

# IpMessageConst, not Android KeyEvent codes.
KEYS = {
    **{str(i): i for i in range(1, 10)},
    "0": 10,
    "up": 11,
    "down": 12,
    "left": 13,
    "right": 14,
    "ok": 15,
    "back": 16,
    "3d": 17,
    "menu": 18,
    "home": 19,
    "power": 20,
    "volume_up": 21,
    "volume_down": 22,
    "mute": 23,
    "guide": 24,
    "display": 25,
    "playback": 26,
    "channel_up": 27,
    "channel_down": 28,
    "source": 29,
    "scale": 30,
    "picture": 31,
    "favorite": 32,
    "search": 33,
    "red": 34,
    "green": 35,
    "yellow": 36,
    "blue": 37,
    "backspace": 38,
    "mouse_left": 39,
    "mouse_right": 40,
    "info": 41,
    "smart_tv": 45,
    "enter": 68,
    "dot": 75,
}


class ProtocolError(Exception):
    """Malformed or unexpected TV response."""


class UnsupportedEncryption(ProtocolError):
    """A TV negotiated an unimplemented cipher; never downgrade silently."""


def field(value: str, *, maximum: int = 4096) -> str:
    """Reject protocol delimiters rather than inventing undocumented escaping."""
    if not isinstance(value, str) or not value or len(value.encode()) > maximum:
        raise ValueError("Empty or oversized value")
    if ">>" in value or "\x00" in value:
        raise ValueError("MagiConnect values cannot contain >> or NUL")
    return value


def normalize_mac(value: str) -> str | None:
    compact = value.replace("&#058", ":").replace(":", "").replace("-", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact) or compact in {"0" * 12, "f" * 12}:
        return None
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2))


def encrypt(data: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV)).encryptor()
    return cipher.update(padded) + cipher.finalize()


def decrypt(data: bytes) -> bytes:
    try:
        cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV)).decryptor()
        padded = cipher.update(data) + cipher.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as err:
        raise ProtocolError("Invalid AES payload") from err


def frame(message: str, algorithm: int = -1) -> bytes:
    if algorithm not in {-1, 0, 1}:
        raise UnsupportedEncryption("Unsupported algorithm")
    payload = message.encode("utf-8")
    if algorithm == 1:
        payload = encrypt(payload)
    if not 0 < len(payload) < MAX_FRAME:
        raise ValueError("Invalid frame length")
    return struct.pack(">I", len(payload)) + payload


def decode(payload: bytes, algorithm: int) -> str:
    if algorithm not in {-1, 0, 1}:
        raise UnsupportedEncryption("Unsupported algorithm")
    if algorithm == 1:
        payload = decrypt(payload)
    try:
        return payload.decode("utf-8").rstrip("\x00")
    except UnicodeDecodeError as err:
        raise ProtocolError("Invalid UTF-8 response") from err


@dataclass(frozen=True)
class DeviceInfo:
    """Handshake fields: no inference that the panel is powered on."""

    client_type: str
    app_version: str
    software_version: str
    model: str
    mac: str | None
    algorithm: int
    functions: str
    serial: str

    @property
    def unique_id(self) -> str | None:
        return self.mac or (f"serial:{self.serial}" if self.serial else None)


def parse_handshake(message: str) -> DeviceInfo:
    parts = message.split(">>")
    if len(parts) < 6 or parts[0] != "159" or not parts[1]:
        raise ProtocolError("Not a MagiConnect identification response")
    try:
        algorithm = int(parts[6]) if len(parts) > 6 and parts[6] else -1
    except ValueError as err:
        raise ProtocolError("Invalid encryption negotiation") from err
    if algorithm not in {-1, 0, 1}:
        raise UnsupportedEncryption(f"Unsupported algorithm: {algorithm}")
    return DeviceInfo(
        client_type=parts[1],
        app_version=parts[2],
        software_version=parts[3],
        model=parts[4],
        mac=normalize_mac(parts[5]),
        algorithm=algorithm,
        functions=parts[10] if len(parts) > 10 else "",
        serial=parts[12] if len(parts) > 12 else "",
    )


@dataclass(frozen=True)
class DiscoveredDevice:
    host: str
    name: str
    version: int
    mac: str | None


def discovery_message(client_id: str, timestamp_ms: int) -> bytes:
    return f"1:{timestamp_ms}:Home Assistant:PHONE:1:Home Assistant:{client_id}:0:0\x00".encode()


def parse_discovery(data: bytes, host: str) -> DiscoveredDevice | None:
    if len(data) > 4096:
        return None
    try:
        parts = data.rstrip(b"\x00").decode("utf-8").split(":")
        if len(parts) < 6 or parts[3] != "TV" or parts[4] not in {"1", "3", "4"}:
            return None
        version = int(parts[0])
        if version < 1:
            return None
        return DiscoveredDevice(
            host,
            parts[2].replace("&#058", ":"),
            version,
            normalize_mac(parts[8]) if len(parts) > 8 else None,
        )
    except (ValueError, UnicodeDecodeError):
        return None


@dataclass(frozen=True)
class App:
    package: str
    name: str


def parse_apps(message: str) -> list[App]:
    parts = message.split(">>", 2)
    if parts[:2] != ["223", "GET"]:
        raise ProtocolError("Unexpected application response")
    if len(parts) < 3 or not parts[2]:
        return []
    apps = {}
    for row in parts[2].split(">"):
        columns = row.split("::")
        if len(columns) < 3 or not columns[0] or not columns[1]:
            continue
        if re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", columns[0]):
            apps[columns[0]] = App(columns[0], columns[1])
    return sorted(apps.values(), key=lambda app: (app.name.casefold(), app.package))
