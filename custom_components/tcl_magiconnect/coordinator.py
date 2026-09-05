"""Poll identity and retain only facts reported by the TV."""

import logging
from datetime import timedelta

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import CannotConnect
from .const import DOMAIN
from .protocol import ProtocolError

_LOGGER = logging.getLogger(__name__)


class MagiConnectCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=30),
            always_update=False,
        )
        self.client = client
        self.apps = []
        self.apps_loaded = False

    async def _async_update_data(self):
        try:
            info = await self.client.identify()
            if self.config_entry.unique_id and info.unique_id != self.config_entry.unique_id:
                raise ProtocolError("A different TV answered at the configured address")
            return info
        except (CannotConnect, ProtocolError) as err:
            raise UpdateFailed(str(err)) from err

    async def execute(self, method, *args, **kwargs):
        """Translate errors and do not retry commands with side effects."""
        try:
            result = await method(*args, **kwargs)
        except (CannotConnect, ProtocolError, ValueError) as err:
            if isinstance(err, (CannotConnect, ProtocolError)):
                self.async_set_update_error(UpdateFailed(str(err)))
            raise HomeAssistantError(str(err)) from err
        if self.client.info:
            self.async_set_updated_data(self.client.info)
        return result

    async def refresh_apps(self):
        self.apps = await self.execute(self.client.get_apps)
        self.apps_loaded = True
        self.async_update_listeners()
