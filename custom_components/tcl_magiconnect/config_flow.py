"""Native discovery, verified manual setup and address reconfiguration."""

from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers import config_validation as cv

from .client import CannotConnect, MagiConnectClient
from .const import CONF_CLIENT_ID, DOMAIN, NAME
from .discovery import discover
from .protocol import ProtocolError, UnsupportedEncryption


class MagiConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._client_id = uuid4().hex
        self._devices = {}

    async def async_step_user(self, user_input=None):
        return self.async_show_menu(step_id="user", menu_options=["manual", "discover"])

    async def async_step_discover(self, user_input=None):
        if user_input is not None:
            device = self._devices[user_input[CONF_HOST]]
            return await self.async_step_manual({CONF_HOST: device.host, CONF_NAME: device.name})
        try:
            self._devices = {d.host: d for d in await discover(self._client_id)}
        except OSError:
            return self.async_abort(reason="discovery_failed")
        if not self._devices:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): vol.In(
                        {h: f"{d.name} ({h})" for h, d in self._devices.items()}
                    )
                }
            ),
        )

    async def async_step_manual(self, user_input=None):
        return await self._configure(user_input, reconfigure=False)

    async def async_step_reconfigure(self, user_input=None):
        return await self._configure(user_input, reconfigure=True)

    async def _configure(self, user_input, *, reconfigure):
        errors = {}
        entry = self._get_reconfigure_entry() if reconfigure else None
        defaults = user_input or (dict(entry.data) if entry else {})
        if user_input is not None:
            host = user_input[CONF_HOST].strip().lower()
            client_id = entry.data[CONF_CLIENT_ID] if entry else self._client_id
            client = MagiConnectClient(host, client_id)
            try:
                info = await client.identify()
            except UnsupportedEncryption:
                errors["base"] = "unsupported_encryption"
            except ProtocolError:
                errors["base"] = "invalid_protocol"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                if info.unique_id:
                    await self.async_set_unique_id(info.unique_id)
                    if reconfigure:
                        self._abort_if_unique_id_mismatch()
                    else:
                        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                elif reconfigure and entry.unique_id:
                    return self.async_abort(reason="wrong_device")
                # IP is a duplicate guard, never a permanent device unique ID.
                if any(
                    e.entry_id != (entry.entry_id if entry else None)
                    and e.data.get(CONF_HOST) == host
                    for e in self._async_current_entries()
                ):
                    return self.async_abort(reason="already_configured")
                data = {
                    CONF_HOST: host,
                    CONF_NAME: user_input.get(CONF_NAME) or NAME,
                    CONF_CLIENT_ID: client_id,
                }
                if reconfigure:
                    return self.async_update_reload_and_abort(entry, data=data)
                return self.async_create_entry(title=data[CONF_NAME], data=data)
            finally:
                await client.close()
        return self.async_show_form(
            step_id="reconfigure" if reconfigure else "manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): cv.string,
                    vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, NAME)): cv.string,
                }
            ),
            errors=errors,
        )
