from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from pyflowlauncher import Result

import actions
import app
from client import AuthFailed, MAError, NotConfigured, Unreachable
from models import MediaItem, Player, absolute_url, image_url

TYPE_LABELS = {
    "track": "Track",
    "album": "Album",
    "artist": "Artist",
    "playlist": "Playlist",
    "radio": "Radio",
    "podcast": "Podcast",
    "podcast_episode": "Episode",
    "audiobook": "Audiobook",
}
TYPE_ICONS = {"radio": "radio", "podcast": "podcast", "podcast_episode": "podcast", "audiobook": "audiobook"}
RADIO_SEED_TYPES = {"track", "album", "artist", "playlist"}
STATE_LABELS = {"playing": "Playing", "paused": "Paused", "idle": "Idle"}
TRANSPORT_TITLES = {
    "play": "Play",
    "pause": "Pause",
    "stop": "Stop",
    "next": "Next track",
    "previous": "Previous track",
}


@dataclass(frozen=True)
class Target:
    base_url: str
    player: Player
    others: Tuple[Player, ...]


def _join(*parts: Optional[str]) -> str:
    return " · ".join(part for part in parts if part)


def clock(seconds: float) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"


def long_duration(seconds: float) -> str:
    hours, minutes = divmod(max(1, round(seconds / 60)), 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    return f"{hours} h" if hours else f"{minutes} min"


def _time_left(item: MediaItem) -> Optional[str]:
    if item.fully_played or not item.resume_position_ms or not item.duration:
        return None
    left = item.duration - item.resume_position_ms / 1000
    return f"{long_duration(left)} left" if left > 0 else None


def _date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        return None
    return f"{date.day} {date:%b %Y}"


def media_subtitle(item: MediaItem) -> str:
    kind = item.media_type
    label = TYPE_LABELS.get(kind) or kind.replace("_", " ").capitalize()
    duration = long_duration(item.duration) if item.duration else None
    if kind == "track":
        return _join(label, ", ".join(item.artists), item.album)
    if kind == "album":
        return _join(label, ", ".join(item.artists))
    if kind == "playlist":
        return _join(label, item.owner)
    if kind == "podcast":
        return _join(label, item.publisher)
    if kind == "audiobook":
        return _join(label, ", ".join(item.authors), duration, _time_left(item))
    if kind == "podcast_episode":
        return _join(_date(item.release_date), duration, _time_left(item)) or label
    return label


def _art(target: Target, item: MediaItem) -> str:
    return image_url(target.base_url, item.image) or app.icon(TYPE_ICONS.get(item.media_type, "music"))


def _player_icon(player: Player) -> str:
    return app.icon("group" if player.is_group else "speaker")


def _play(title: str, subtitle: str, icon: str, player: Player, uri: str,
          option: str = "play", radio: bool = False) -> Result:
    return Result(title=title, subtitle=subtitle, icon=icon).add_action(
        actions.play_media, [player.player_id, player.name, uri, option, radio])


def media_menu(item: MediaItem, target: Target) -> List[Result]:
    player = target.player
    where = f"On {player.name}"
    menu: List[Result] = []
    if item.media_type == "podcast":
        menu.append(Result(title="Play latest episode", subtitle=where, icon=app.icon("podcast")).add_action(
            actions.play_latest_episode, [player.player_id, player.name, item.item_id, item.provider, item.name]))
    menu += [
        _play("Play now", where, app.icon("play"), player, item.uri),
        _play("Play next", where, app.icon("next"), player, item.uri, "next"),
        _play("Add to queue", where, app.icon("queue"), player, item.uri, "add"),
    ]
    if item.media_type in RADIO_SEED_TYPES:
        menu.append(_play("Start radio", f"Similar music on {player.name}", app.icon("radio"),
                          player, item.uri, radio=True))
    for other in target.others:
        menu.append(_play(f"Play on {other.name}", item.name, _player_icon(other), other, item.uri))
    return menu


def media_result(item: MediaItem, target: Target, subtitle: Optional[str] = None) -> Result:
    result = Result(title=item.name, subtitle=subtitle or media_subtitle(item), icon=_art(target, item),
                    context_data=media_menu(item, target))
    if item.media_type == "podcast":
        return result.add_action(actions.change_query, [app.full_query(f"podcast {item.name}")])
    player = target.player
    return result.add_action(actions.play_media, [player.player_id, player.name, item.uri, "play", False])


def player_result(player: Player, active_id: Optional[str]) -> Result:
    playing = player.now_playing
    subtitle = _join(
        "Active" if player.player_id == active_id else None,
        STATE_LABELS.get(player.state, player.state.capitalize()),
        playing.title if playing else None,
        playing.artist if playing else None,
    )
    return Result(title=player.name, subtitle=subtitle, icon=_player_icon(player)).add_action(
        actions.set_active, [player.player_id])


def now_playing_result(target: Target) -> Result:
    player = target.player
    playing = player.now_playing
    toggle = [player.player_id, player.name, "play_pause"]
    menu = now_playing_menu(player)
    if playing is None:
        return Result(title=f"Nothing playing on {player.name}", subtitle=STATE_LABELS.get(player.state, ""),
                      icon=app.icon("music"), context_data=menu).add_action(actions.player_cmd, toggle)
    progress = None
    if playing.duration:
        progress = f"{clock(playing.elapsed or 0)} / {clock(playing.duration)}"
    elif playing.elapsed:
        progress = clock(playing.elapsed)
    subtitle = _join("Paused" if player.state == "paused" else None, playing.artist, player.name, progress)
    icon = absolute_url(target.base_url, playing.image_url) or app.icon("music")
    return Result(title=playing.title, subtitle=subtitle, icon=icon,
                  context_data=menu).add_action(actions.player_cmd, toggle)


def now_playing_menu(player: Player) -> List[Result]:
    toggle = "pause" if player.playing else "play"
    return [
        transport_result(player, toggle),
        transport_result(player, "next"),
        transport_result(player, "previous"),
        transport_result(player, "stop"),
        volume_row(player),
        volume_step(player, "up"),
        volume_step(player, "down"),
        mute_result(player),
    ]


def transport_result(player: Player, command: str) -> Result:
    playing = player.now_playing
    subtitle = _join(playing.title, playing.artist) if playing else ""
    return Result(title=f"{TRANSPORT_TITLES[command]} on {player.name}", subtitle=subtitle,
                  icon=app.icon(command)).add_action(actions.player_cmd, [player.player_id, player.name, command])


def volume_row(player: Player, keyword_row: bool = False) -> Result:
    title = f"Volume {player.volume}%" if player.volume is not None else "Volume unknown"
    if keyword_row:
        return Result(title=title, subtitle=f"{player.name} · type a level, for example vol 40",
                      icon=app.icon("volume")).add_action(actions.keep_open)
    return Result(title=title, subtitle=f"{player.name} · Enter to change", icon=app.icon("volume")).add_action(
        actions.change_query, [app.full_query("vol ")])


def volume_step(player: Player, direction: str) -> Result:
    return Result(title=f"Volume {direction}", subtitle=f"On {player.name}", icon=app.icon("volume")).add_action(
        actions.player_cmd, [player.player_id, player.name, f"volume_{direction}"])


def mute_result(player: Player) -> Result:
    muted = bool(player.muted)
    title = f"Unmute {player.name}" if muted else f"Mute {player.name}"
    return Result(title=title, subtitle="", icon=app.icon("volume" if muted else "mute")).add_action(
        actions.set_mute, [player.player_id, player.name, not muted])


def switch_player_result(player: Player) -> Result:
    return Result(title=f"Player: {player.name}", subtitle="Switch to another player",
                  icon=_player_icon(player)).add_action(actions.change_query, [app.full_query("players ")])


def message_result(title: str, subtitle: str = "", icon_name: str = "warning") -> Result:
    return Result(title=title, subtitle=subtitle, icon=app.icon(icon_name)).add_action(actions.keep_open)


def error_result(error: MAError, base_url: str) -> Result:
    if isinstance(error, NotConfigured):
        return Result(title="Set up Music Assistant", subtitle=str(error), icon=app.icon("settings")).add_action(
            actions.open_settings)
    if isinstance(error, AuthFailed):
        return Result(title="Music Assistant rejected the token",
                      subtitle="Create a new long-lived token in Music Assistant and paste it in the plugin settings",
                      icon=app.icon("settings")).add_action(actions.open_settings)
    if isinstance(error, Unreachable):
        return message_result(f"Can't reach {base_url or 'Music Assistant'}", str(error))
    return message_result("Music Assistant error", str(error))


def order_search(items: List[MediaItem], text: str) -> List[MediaItem]:
    wanted = text.strip().lower()
    return sorted(items, key=lambda item: item.name.lower() != wanted)
