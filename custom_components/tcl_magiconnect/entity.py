"""Shared device registry information."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class MagiConnectEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, suffix):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._entry = entry

    @property
    def device_info(self):
        info = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.unique_id or self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="TCL",
            model=info.model or None,
            sw_version=info.software_version or None,
        )
