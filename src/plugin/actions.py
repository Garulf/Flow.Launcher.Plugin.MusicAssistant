from typing import Awaitable, Callable

import app
from client import MAClient, MAError
from launcher import KEEP_OPEN
from models import MediaItem

plugin = app.plugin
COMMAND_VERBS = {
    "play": "play",
    "pause": "pause",
    "play_pause": "play or pause",
    "stop": "stop",
    "next": "skip to the next track",
    "previous": "go back a track",
    "volume_up": "turn the volume up",
    "volume_down": "turn the volume down",
}


async def _notify(title: str, subtitle: str) -> None:
    api = plugin.launcher.api
    await api.invoke(api.show_msg(title, subtitle, app.ICON))


async def _run(verb: str, player_name: str, operation: Callable[[MAClient], Awaitable[None]]) -> None:
    try:
        await operation(app.session.client(plugin.settings))
    except Exception as error:
        if not isinstance(error, MAError):
            plugin.logger.exception("Couldn't %s on %s", verb, player_name)
        await _notify(f"Couldn't {verb} on {player_name}", str(error) or type(error).__name__)


@plugin.on_method
async def play_media(player_id: str, player_name: str, uri: str, option: str = "play", radio: bool = False):
    await _run("play", player_name, lambda client: client.play_media(player_id, uri, option, radio))


@plugin.on_method
async def play_latest_episode(player_id: str, player_name: str, item_id: str, provider: str, name: str):
    async def play_latest(client: MAClient) -> None:
        episodes = await client.podcast_episodes(MediaItem(item_id, provider, name, "", "podcast"))
        if not episodes:
            raise MAError(f"{name} has no episodes")
        await client.play_media(player_id, episodes[0].uri)

    await _run("play", player_name, play_latest)


@plugin.on_method
async def player_cmd(player_id: str, player_name: str, command: str):
    verb = COMMAND_VERBS.get(command, command.replace("_", " "))
    await _run(verb, player_name, lambda client: client.player_cmd(player_id, command))


@plugin.on_method
async def set_volume(player_id: str, player_name: str, level: int):
    await _run("change the volume", player_name,
               lambda client: client.player_cmd(player_id, "volume_set", volume_level=int(level)))


@plugin.on_method
async def set_mute(player_id: str, player_name: str, muted: bool):
    verb = "mute" if muted else "unmute"
    await _run(verb, player_name, lambda client: client.player_cmd(player_id, "volume_mute", muted=bool(muted)))


@plugin.on_method
async def set_active(player_id: str):
    app.active_store.set(player_id)
    return await change_query(app.full_query(""))


@plugin.on_method
async def change_query(query: str):
    api = plugin.launcher.api
    await api.invoke(api.change_query(query))
    return KEEP_OPEN


@plugin.on_method
async def open_settings():
    api = plugin.launcher.api
    await api.invoke(api.open_setting_dialog())


@plugin.on_method
async def keep_open():
    """Flow Launcher 2.1.4 crashes when a python_v2 result without an action is selected."""
    return KEEP_OPEN
