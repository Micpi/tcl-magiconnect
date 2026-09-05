"""A diagnostic sensor explicitly reporting the service, not panel power."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory

from .entity import MagiConnectEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MagiConnectServiceSensor(entry.runtime_data, entry)])


class MagiConnectServiceSensor(MagiConnectEntity, SensorEntity):
    _attr_name = "MagiConnect service"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "service")

    @property
    def native_value(self):
        return "reachable"

    @property
    def extra_state_attributes(self):
        info = self.coordinator.data
        return {
            "transport": "TCP 6553",
            "encryption": "AES-CBC" if info.algorithm == 1 else "plaintext",
            "service_version": info.app_version,
            "applications_loaded": self.coordinator.apps_loaded,
        }
