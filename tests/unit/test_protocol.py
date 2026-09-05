"""Known wire examples and hostile/truncated input regression coverage."""

import struct

import pytest
from magiconnect_wire.protocol import (
    KEYS,
    MAX_FRAME,
    ProtocolError,
    UnsupportedEncryption,
    decode,
    decrypt,
    discovery_message,
    encrypt,
    field,
    frame,
    normalize_mac,
    parse_apps,
    parse_discovery,
    parse_handshake,
)

HELLO = "159>>ANDROID>>20170412:2.0>>firmware>>Model>>AA:BB:CC:DD:EE:FF>>1"


def test_handshake():
    info = parse_handshake(HELLO)
    assert info.mac == "aa:bb:cc:dd:ee:ff"
    assert info.algorithm == 1
    assert info.model == "Model"
    assert info.unique_id == info.mac
    assert parse_handshake(HELLO.rsplit(">>", 1)[0]).algorithm == -1


@pytest.mark.parametrize("message", ["HTTP/1.1 200 OK", "159>>", "159>>TV", "150>>YES"])
def test_not_identification(message):
    with pytest.raises(ProtocolError):
        parse_handshake(message)


@pytest.mark.parametrize("algorithm", ["2", "-2", "99"])
def test_never_downgrade_unknown_cipher(algorithm):
    with pytest.raises(UnsupportedEncryption):
        parse_handshake(HELLO.rsplit(">>", 1)[0] + ">>" + algorithm)


def test_native_key_codes_are_not_android_codes():
    assert KEYS["ok"] == 15
    assert KEYS["enter"] == 68
    assert KEYS["0"] == 10
    assert KEYS["home"] == 19


def test_discovery():
    data = b"6:123:Salon&#058TV:TV:3:Salon:101010:0:AA&#058BB&#058CC&#058DD&#058EE&#058FF\x00"
    tv = parse_discovery(data, "192.0.2.1")
    assert tv.name == "Salon:TV"
    assert tv.mac == "aa:bb:cc:dd:ee:ff"
    assert tv.version == 6
    assert (
        discovery_message("abc", 123) == b"1:123:Home Assistant:PHONE:1:Home Assistant:abc:0:0\x00"
    )


@pytest.mark.parametrize(
    "data", [b"", b"\xff", b"1:2:Phone:PHONE:1:name", b"1:2:TV:TV:2:name", b"a:2:TV:TV:3:name"]
)
def test_discovery_rejects_invalid_or_departing_devices(data):
    assert parse_discovery(data, "192.0.2.1") is None


@pytest.mark.parametrize("value", ["00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff", "not-a-mac"])
def test_bad_mac(value):
    assert normalize_mac(value) is None


def test_utf8_frame_length_and_encryption():
    message = "155>>Télévision 🎬"
    assert struct.unpack(">I", frame(message)[:4])[0] == len(message.encode())
    assert decode(frame(message, 1)[4:], 1) == message
    assert decrypt(encrypt(b"149>>15")) == b"149>>15"


def test_corrupt_encryption():
    with pytest.raises(ProtocolError):
        decrypt(b"invalid")
    with pytest.raises(ValueError):
        frame("x" * MAX_FRAME)


@pytest.mark.parametrize("value", ["", "text>>149>>20", "hello\x00world", "x" * 4097])
def test_protocol_delimiter_injection(value):
    with pytest.raises(ValueError):
        field(value)


def test_apps_native_delimiters_and_duplicates():
    apps = parse_apps(
        "223>>GET>>org.example.tv::Example::icon::1::v1::0::0::0::1>bad>org.example.tv::Updated::icon>com.test.app::Test::icon"
    )
    assert [(app.package, app.name) for app in apps] == [
        ("com.test.app", "Test"),
        ("org.example.tv", "Updated"),
    ]
    assert parse_apps("223>>GET>>") == []
    with pytest.raises(ProtocolError):
        parse_apps("223>>OPEN>>org.example.tv")
