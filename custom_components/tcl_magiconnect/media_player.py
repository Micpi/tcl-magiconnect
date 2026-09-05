"""TCL native player controls; no inferred global playback or power state."""

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature
from homeassistant.exceptions import HomeAssistantError

from .entity import MagiConnectEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MagiConnectMediaPlayer(entry.runtime_data, entry)])


class MagiConnectMediaPlayer(MagiConnectEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_icon = "mdi:television"
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
    )

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "media_player")

    @property
    def source_list(self):
        # Package suffix keeps duplicate translated application names distinct.
        return [f"{app.name} ({app.package})" for app in self.coordinator.apps]

    async def async_select_source(self, source):
        for app, label in zip(self.coordinator.apps, self.source_list, strict=True):
            if source in {label, app.package}:
                await self.coordinator.execute(self.coordinator.client.launch_app, app.package)
                return
        raise HomeAssistantError("Unknown application; run tcl_magiconnect.refresh_apps first")

    async def async_volume_up(self):
        await self.coordinator.execute(self.coordinator.client.send_keys, ["volume_up"])

    async def async_volume_down(self):
        await self.coordinator.execute(self.coordinator.client.send_keys, ["volume_down"])

    async def async_media_play(self):
        await self.coordinator.execute(self.coordinator.client.player_command, "play")

    async def async_media_pause(self):
        await self.coordinator.execute(self.coordinator.client.player_command, "pause")

    async def async_media_stop(self):
        await self.coordinator.execute(self.coordinator.client.player_command, "stop")

    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_type != "video":
            raise HomeAssistantError("Only direct video URLs are implemented in this release")
        await self.coordinator.execute(self.coordinator.client.cast_video, media_id)
