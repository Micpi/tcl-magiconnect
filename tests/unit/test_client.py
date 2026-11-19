"""Exercise real TCP streams against a local simulated TV, including AES."""

import asyncio
import struct
from contextlib import asynccontextmanager

import pytest
from magiconnect_wire.client import CannotConnect, MagiConnectClient, RequestTimeout
from magiconnect_wire.protocol import ProtocolError, decode, frame

HELLO = "159>>ANDROID>>20170412:2.0>>firmware>>Model>>AA:BB:CC:DD:EE:FF"


async def read_message(reader, algorithm=-1):
    size = struct.unpack(">I", await reader.readexactly(4))[0]
    return decode(await reader.readexactly(size), algorithm)


@asynccontextmanager
async def tv_server(handler):
    tasks = set()
    errors = []

    async def run(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        try:
            await handler(reader, writer)
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception as err:
            errors.append(err)
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    server = await asyncio.start_server(run, "127.0.0.1", 0)
    client = MagiConnectClient(
        "127.0.0.1", "test-client", server.sockets[0].getsockname()[1], timeout=0.2
    )
    try:
        yield client
    finally:
        await client.close()
        server.close()
        await server.wait_closed()
        if tasks:
            await asyncio.gather(*tasks)
        assert not errors


@pytest.mark.parametrize("algorithm", [-1, 0, 1])
async def test_fragmented_handshake_then_commands(algorithm):
    received = []

    async def handler(reader, writer):
        assert await read_message(reader) == "159>>Home Assistant>>1>>test-client>>1"
        data = frame(HELLO + f">>{algorithm}")
        for chunk in [data[:1], data[1:3], data[3:9], data[9:]]:
            writer.write(chunk)
            await writer.drain()
            await asyncio.sleep(0)
        for _ in range(4):
            received.append(await read_message(reader, algorithm))

    async with tv_server(handler) as client:
        await client.send_keys(["up", "ok"], repeat=2, delay=0)
    assert received == ["149>>11", "149>>15", "149>>11", "149>>15"]


async def test_apps_ignore_heartbeat_and_open_notification():
    async def handler(reader, writer):
        await read_message(reader)
        writer.write(frame(HELLO + ">>1"))
        assert await read_message(reader, 1) == "223>>GET"
        writer.write(
            frame("150>>YES", 1)
            + frame("223>>OPEN>>com.test.app", 1)
            + frame("223>>GET>>com.test.app::Test::icon", 1)
        )
        await writer.drain()

    async with tv_server(handler) as client:
        apps = await client.get_apps()
        assert apps[0].package == "com.test.app"


async def test_encrypted_notification_before_plaintext_identity():
    received = []

    async def handler(reader, writer):
        await read_message(reader)
        writer.write(frame("253>>1>>0", 1) + frame(HELLO + ">>1"))
        await writer.drain()
        received.append(await read_message(reader, 1))

    async with tv_server(handler) as client:
        await client.send_keys(["up"])
    assert received == ["149>>11"]


@pytest.mark.parametrize("payload", [struct.pack(">I", 1048576), struct.pack(">I", 0)])
async def test_bad_length_does_not_allocate(payload):
    async def handler(reader, writer):
        await read_message(reader)
        writer.write(payload)
        await writer.drain()

    async with tv_server(handler) as client:
        with pytest.raises(ProtocolError):
            await client.identify()


async def test_incomplete_frame():
    async def handler(reader, writer):
        await read_message(reader)
        writer.write(b"\x00\x00")

    async with tv_server(handler) as client:
        with pytest.raises(CannotConnect):
            await client.identify()


async def test_timeout_and_cleanup():
    async def handler(reader, writer):
        await read_message(reader)
        assert await reader.read() == b""

    async with tv_server(handler) as client:
        with pytest.raises(RequestTimeout):
            await client.identify()
        assert client._writer is None


async def test_wrong_tv_never_receives_command():
    async def handler(reader, writer):
        await read_message(reader)
        writer.write(frame(HELLO + ">>-1"))
        assert await reader.read() == b""

    async with tv_server(handler) as client:
        client.expected_unique_id = "11:22:33:44:55:66"
        with pytest.raises(ProtocolError):
            await client.send_keys(["power"])


async def test_commands_validate_before_connecting():
    client = MagiConnectClient("127.0.0.1", "test", port=1)
    with pytest.raises(ValueError):
        await client.send_keys(["power", "unverified"])
    with pytest.raises(ValueError):
        await client.send_keys(["up"], repeat=101)
    with pytest.raises(ValueError):
        await client.send_text("hello>>149>>20")
    with pytest.raises(ValueError):
        await client.launch_app("com.test>>UNINSTALL")
    with pytest.raises(ValueError):
        await client.cast_video("file:///etc/passwd")
    with pytest.raises(ValueError):
        await client.move_mouse(1000000, 0)
    await client.close()


async def test_new_session_renegotiates_cipher():
    seen = []
    count = 0

    async def handler(reader, writer):
        nonlocal count
        algorithm = count
        count += 1
        await read_message(reader)
        writer.write(frame(HELLO + f">>{algorithm}"))
        seen.append(await read_message(reader, algorithm))

    async with tv_server(handler) as client:
        await client.send_text("été")
        await client.launch_app("com.example.tv")
    assert seen == ["155>>été", "223>>OPEN>>com.example.tv"]


@pytest.mark.parametrize("url", ["http://evil.example/screen.jpg", "file:///tmp/test"])
async def test_reject_foreign_screenshot_url(url):
    async def handler(reader, writer):
        await read_message(reader)
        writer.write(frame(HELLO + ">>-1"))
        assert await read_message(reader) == "225>>"
        writer.write(frame(f"225>>0>>{url}"))

    async with tv_server(handler) as client:
        with pytest.raises(ProtocolError):
            await client.get_screenshot_url()


async def test_cast_wire_order():
    messages = []

    async def handler(reader, writer):
        await read_message(reader)
        writer.write(frame(HELLO + ">>-1"))
        for _ in range(3):
            messages.append(await read_message(reader))

    async with tv_server(handler) as client:
        await client.cast_video("https://example.com/video.mp4", "Film")
    assert messages == [
        "129>>",
        "133>>Video",
        "134>>https://example.com/video.mp4->Film->null->null->null->false->null->null",
    ]
