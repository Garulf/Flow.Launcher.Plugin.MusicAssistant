import asyncio
from typing import Iterable, List, Optional

from pyflowlauncher import Result

import actions
import app
import results as r
from client import MAClient, MAError, normalize_url
from commands import Dashboard, Library, Mute, Players, Route, Search, Transport, Volume, parse
from models import MediaItem, Player
from state import choose_active

plugin = app.plugin
SCORE_STEP = 1000
EPISODE_LIMIT = 50
LIBRARY_NAMES = {
    "playlists": "playlists",
    "radio": "radio stations",
    "albums": "albums",
    "artists": "artists",
    "tracks": "tracks",
    "audiobooks": "audiobooks",
    "podcasts": "podcasts",
    "favorites": "favorites",
}


@plugin.on_method
async def query(query: str) -> List[Result]:
    try:
        found = await respond(parse(query))
    except MAError as error:
        found = [r.error_result(error, normalize_url(str(plugin.settings.get("server_url") or "")))]
    except Exception as error:
        plugin.logger.exception("Query %r failed", query)
        found = [r.message_result("Music Assistant error", str(error) or type(error).__name__)]
    for index, result in enumerate(found):
        result.score = (len(found) - index) * SCORE_STEP
    return found


async def respond(route: Route) -> List[Result]:
    client = app.session.client(plugin.settings)
    players = await client.players()
    active = choose_active(players, app.active_store.get())
    if isinstance(route, Players):
        return players_view(players, active.player_id if active else None, route.filter)
    if active is None:
        return [no_players()]
    others = tuple(p for p in players if p.available and p.player_id != active.player_id)
    target = r.Target(client.base_url, active, others)
    if isinstance(route, Dashboard):
        return await dashboard(client, target)
    if isinstance(route, Search):
        found = r.order_search(await client.search(route.text), route.text)
        return media_list(found, target, f'No results for "{route.text}"')
    if isinstance(route, Transport):
        return [r.transport_result(active, route.command)]
    if isinstance(route, Volume):
        return volume_view(active, route)
    if isinstance(route, Mute):
        return [r.mute_result(active)]
    if isinstance(route, Library):
        return await library_view(client, target, route)
    return await episodes_view(client, target, route.podcast)


def no_players() -> Result:
    return r.message_result("No players available", "Check your players in Music Assistant", "speaker")


async def dashboard(client: MAClient, target: r.Target) -> List[Result]:
    progress, recents = await asyncio.gather(client.in_progress(), client.recently_played(), return_exceptions=True)
    if isinstance(progress, BaseException):
        plugin.logger.warning("Continue listening unavailable: %s", progress)
        progress = []
    if isinstance(recents, BaseException):
        plugin.logger.warning("Recently played unavailable: %s", recents)
        recents = []
    rows = [r.now_playing_result(target), r.switch_player_result(target.player)]
    rows += [r.media_result(item, target, f"Continue listening · {r.media_subtitle(item)}")
             for item in progress[:3]]
    return rows + media_list(recents, target, None)


def media_list(items: Iterable[MediaItem], target: r.Target, empty: Optional[str]) -> List[Result]:
    items = list(items)
    for item in items:
        if item.media_type == "podcast":
            app.podcasts_seen[item.name.lower()] = item
    if not items:
        return [r.message_result(empty, icon_name="music")] if empty else []
    return [r.media_result(item, target) for item in items]


def players_view(players: List[Player], active_id: Optional[str], name_filter: str) -> List[Result]:
    wanted = name_filter.lower()
    shown = [p for p in players if p.available and wanted in p.name.lower()]
    if not shown:
        return [r.message_result(f'No players match "{name_filter}"', icon_name="speaker")] if name_filter \
            else [no_players()]
    shown.sort(key=lambda p: (p.player_id != active_id, not p.playing, p.state != "paused", p.name.lower()))
    return [r.player_result(p, active_id) for p in shown]


def volume_view(player: Player, route: Volume) -> List[Result]:
    if route.level is None and route.delta is None:
        return [r.volume_row(player, keyword_row=True), r.volume_step(player, "up"), r.volume_step(player, "down")]
    level = route.level if route.level is not None else (player.volume or 0) + (route.delta or 0)
    level = max(0, min(100, level))
    current = f"Currently {player.volume}%" if player.volume is not None else ""
    return [Result(title=f"Set {player.name} volume to {level}%", subtitle=current,
                   icon=app.icon("volume")).add_action(actions.set_volume, [player.player_id, player.name, level])]


async def library_view(client: MAClient, target: r.Target, route: Library) -> List[Result]:
    if route.kind == "favorites":
        items = await client.favorites(route.filter)
    else:
        items = await client.library(route.kind, route.filter)
    empty = f'No results for "{route.filter}"' if route.filter else f"No {LIBRARY_NAMES[route.kind]} in your library"
    return media_list(items, target, empty)


async def episodes_view(client: MAClient, target: r.Target, name: str) -> List[Result]:
    podcast = app.podcasts_seen.get(name.lower())
    if podcast is None:
        matches = [p for p in await client.library("podcasts", name) if p.name.lower() == name.lower()]
        podcast = matches[0] if matches else None
    if podcast is None:
        return [r.message_result(f'No podcast named "{name}"', icon_name="podcast")]
    episodes = await client.podcast_episodes(podcast)
    return media_list(episodes[:EPISODE_LIMIT], target, f"{podcast.name} has no episodes")
