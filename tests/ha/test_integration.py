"""Config flow, entity services, unloading and failure handling in HA itself."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tcl_magiconnect.client import CannotConnect
from custom_components.tcl_magiconnect.diagnostics import async_get_config_entry_diagnostics
from custom_components.tcl_magiconnect.protocol import App

DOMAIN = "tcl_magiconnect"


async def setup(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TCL Test",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"host": "192.0.2.1", "name": "TCL Test", "client_id": "test"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    return entry, {entity.domain: entity.entity_id for entity in entities}


async def test_manual_flow_and_duplicate(hass, client):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["step_id"] == "manual"
    with patch("custom_components.tcl_magiconnect.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.1", "name": "Salon"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
        await hass.async_block_till_done()
    again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    again = await hass.config_entries.flow.async_configure(
        again["flow_id"], {"next_step_id": "manual"}
    )
    again = await hass.config_entries.flow.async_configure(again["flow_id"], {"host": "192.0.2.1"})
    assert again["reason"] == "already_configured"


async def test_unreachable_setup_form(hass, client):
    client.identify.side_effect = CannotConnect("Offline")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.1"}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    client.close.assert_awaited()


async def test_entities_and_native_services(hass, client):
    entry, entities = await setup(hass)
    assert entry.state == ConfigEntryState.LOADED
    assert hass.states.get(entities["remote"]).state == STATE_UNKNOWN
    assert hass.states.get(entities["media_player"]).state == STATE_UNKNOWN
    assert hass.states.get(entities["sensor"]).state == "reachable"
    await hass.services.async_call(
        "remote",
        "send_command",
        {"entity_id": entities["remote"], "command": ["up", "ok"]},
        blocking=True,
    )
    client.send_keys.assert_awaited_once()
    await hass.services.async_call(
        DOMAIN, "send_text", {"entity_id": entities["remote"], "text": "Bonjour"}, blocking=True
    )
    client.send_text.assert_awaited_once_with("Bonjour")
    response = await hass.services.async_call(
        DOMAIN,
        "get_screenshot_url",
        {"entity_id": entities["remote"]},
        blocking=True,
        return_response=True,
    )
    assert "http://192.0.2.1/screen.jpg" in str(response)
    client.get_apps.return_value = [App("com.example.tv", "Example")]
    await hass.services.async_call(
        DOMAIN, "refresh_apps", {"entity_id": entities["remote"]}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get(entities["media_player"])
    assert state.attributes["source_list"] == ["Example (com.example.tv)"]
    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": entities["media_player"], "source": "Example (com.example.tv)"},
        blocking=True,
    )
    client.launch_app.assert_awaited_once_with("com.example.tv")
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert "192.0.2.1" not in str(diagnostics)
    assert "aa:bb:cc:dd:ee:ff" not in str(diagnostics)
    assert "Bonjour" not in str(diagnostics)
    assert await hass.config_entries.async_unload(entry.entry_id)
    client.close.assert_awaited_once()


async def test_command_failure_marks_unavailable(hass, client):
    entry, entities = await setup(hass)
    client.send_keys.side_effect = CannotConnect("Disconnected")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "remote",
            "send_command",
            {"entity_id": entities["remote"], "command": ["power"]},
            blocking=True,
        )
    assert not entry.runtime_data.last_update_success
    assert client.send_keys.await_count == 1
    await hass.config_entries.async_unload(entry.entry_id)


async def test_initial_failure_retries(hass, client):
    client.identify.side_effect = CannotConnect("Offline")
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.0.2.1", "client_id": "test"})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY
    client.close.assert_awaited_once()


async def test_discovery_no_devices(hass, client):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    with patch(
        "custom_components.tcl_magiconnect.config_flow.discover", AsyncMock(return_value=[])
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
    assert result["reason"] == "no_devices_found"
