"""Real Home Assistant fixtures; transport is replaced by a simulated client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tcl_magiconnect.protocol import DeviceInfo


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def client():
    info = DeviceInfo("ANDROID", "20170412:2.0", "test", "TCL Test", "aa:bb:cc:dd:ee:ff", 1, "", "")
    client = MagicMock()
    client.info = info
    client.identify = AsyncMock(return_value=info)
    client.close = AsyncMock()
    for method in [
        "send_keys",
        "send_text",
        "launch_app",
        "move_mouse",
        "player_command",
        "cast_video",
    ]:
        setattr(client, method, AsyncMock())
    client.get_apps = AsyncMock(return_value=[])
    client.get_screenshot_url = AsyncMock(return_value="http://192.0.2.1/screen.jpg")
    with (
        patch("custom_components.tcl_magiconnect.MagiConnectClient", return_value=client),
        patch(
            "custom_components.tcl_magiconnect.config_flow.MagiConnectClient", return_value=client
        ),
    ):
        yield client
