"""Local TCL MagiConnect integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .client import MagiConnectClient
from .const import CONF_CLIENT_ID
from .coordinator import MagiConnectCoordinator

PLATFORMS = [Platform.REMOTE, Platform.MEDIA_PLAYER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = MagiConnectClient(entry.data["host"], entry.data[CONF_CLIENT_ID])
    client.expected_unique_id = entry.unique_id
    coordinator = MagiConnectCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await client.close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()
        return True
    return False
