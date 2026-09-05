"""Native remote and explicit advanced actions."""

import voluptuous as vol
from homeassistant.components.remote import RemoteEntity
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform

from .entity import MagiConnectEntity
from .protocol import KEYS


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MagiConnectRemote(entry.runtime_data, entry)])
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "send_text", {vol.Required("text"): cv.string}, "async_send_text"
    )
    platform.async_register_entity_service(
        "move_mouse",
        {
            vol.Required("x"): vol.All(vol.Coerce(int), vol.Range(min=-2000, max=2000)),
            vol.Required("y"): vol.All(vol.Coerce(int), vol.Range(min=-2000, max=2000)),
        },
        "async_move_mouse",
    )
    platform.async_register_entity_service(
        "launch_app", {vol.Required("package"): cv.string}, "async_launch_app"
    )
    platform.async_register_entity_service("refresh_apps", {}, "async_refresh_apps")
    platform.async_register_entity_service(
        "get_screenshot_url",
        {},
        "async_get_screenshot_url",
        supports_response=SupportsResponse.ONLY,
    )


class MagiConnectRemote(MagiConnectEntity, RemoteEntity):
    _attr_name = "Remote"
    _attr_icon = "mdi:remote-tv"
    _attr_is_on = None

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "remote")

    @property
    def extra_state_attributes(self):
        return {"commands": sorted(KEYS), "power_state_reported": False}

    async def async_send_command(self, command, **kwargs):
        if kwargs.get("hold_secs", 0):
            raise HomeAssistantError("Long press is not verified; use num_repeats instead")
        commands = [command] if isinstance(command, str) else list(command)
        await self.coordinator.execute(
            self.coordinator.client.send_keys,
            commands,
            repeat=kwargs.get("num_repeats", 1),
            delay=kwargs.get("delay_secs", 0.15),
        )

    async def async_turn_on(self, **kwargs):
        raise HomeAssistantError("Power state is unknown; use send_command with power to toggle")

    async def async_turn_off(self, **kwargs):
        raise HomeAssistantError("Power state is unknown; use send_command with power to toggle")

    async def async_toggle(self, **kwargs):
        await self.async_send_command(["power"])

    async def async_send_text(self, text):
        await self.coordinator.execute(self.coordinator.client.send_text, text)

    async def async_move_mouse(self, x, y):
        await self.coordinator.execute(self.coordinator.client.move_mouse, x, y)

    async def async_launch_app(self, package):
        await self.coordinator.execute(self.coordinator.client.launch_app, package)

    async def async_refresh_apps(self):
        await self.coordinator.refresh_apps()

    async def async_get_screenshot_url(self):
        return {"url": await self.coordinator.execute(self.coordinator.client.get_screenshot_url)}
