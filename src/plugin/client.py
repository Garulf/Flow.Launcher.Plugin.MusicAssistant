import asyncio
import time
import uuid
from urllib.parse import urlsplit
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from models import MediaItem, Player

SEARCH_TYPES = ("artist", "album", "track", "playlist", "radio", "podcast", "audiobook")
SEARCH_KEYS = ("artists", "albums", "tracks", "playlists", "radio", "podcasts", "audiobooks")
LIBRARY_COMMANDS = {
    "playlists": "playlists",
    "radio": "radios",
    "albums": "albums",
    "artists": "artists",
    "tracks": "tracks",
    "audiobooks": "audiobooks",
    "podcasts": "podcasts",
}
PLAYERS_TTL = 2.0
SEARCH_TTL = 30.0
TIMEOUT = 10.0


class MAError(Exception):
    pass


class NotConfigured(MAError):
    pass


class AuthFailed(MAError):
    pass


class Unreachable(MAError):
    pass


class ServerError(MAError):
    pass


def normalize_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and "://" not in url:
        url = f"http://{url}"
    return url


def _is_valid_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return bool(parts.hostname) and parts.port != 0
    except ValueError:
        return False


def _items(raw: Any) -> List[MediaItem]:
    return [MediaItem.from_dict(item) for item in raw or [] if isinstance(item, dict)]


class MAClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        library_only: bool = False,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = normalize_url(base_url)
        self.library_only = library_only
        self._clock = clock
        if not _is_valid_url(self.base_url):
            raise NotConfigured(f"{base_url.strip()} is not a valid server URL")
        if not token.isascii():
            raise NotConfigured("The token has characters a token can't contain. Paste it again.")
        try:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT,
                transport=transport,
            )
        except (httpx.InvalidURL, ValueError) as error:
            raise NotConfigured(f"{base_url.strip()} is not a valid server URL") from error
        self._players: Optional[Tuple[float, List[Player]]] = None
        self._searches: Dict[Tuple[str, bool], Tuple[float, List[MediaItem]]] = {}

    async def call(self, command: str, **args: Any) -> Any:
        payload = {"message_id": uuid.uuid4().hex, "command": command, "args": args}
        try:
            response = await self._http.post("/api", json=payload)
        except httpx.TimeoutException as error:
            raise Unreachable("The server took too long to answer") from error
        except (httpx.HTTPError, httpx.InvalidURL) as error:
            raise Unreachable(str(error) or type(error).__name__) from error
        if 300 <= response.status_code < 400:
            target = response.headers.get("Location", "another address")
            raise Unreachable(f"The server redirected to {target}. Use that address in the plugin settings.")
        if response.status_code == 401:
            raise AuthFailed(response.text.strip() or "Authentication failed")
        if response.status_code >= 400:
            raise ServerError(response.text.strip() or f"HTTP {response.status_code}")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise ServerError("The server sent an unexpected response") from error

    async def players(self) -> List[Player]:
        now = self._clock()
        if self._players and now - self._players[0] < PLAYERS_TTL:
            return self._players[1]
        raw = await self.call("players/all")
        wall_clock = time.time()
        players = [
            Player.from_dict(item, wall_clock)
            for item in raw or []
            if isinstance(item, dict) and item.get("player_id") and not item.get("hide_in_ui")
        ]
        self._players = (now, players)
        return players

    def invalidate_players(self) -> None:
        self._players = None

    async def search(self, text: str, limit: int = 5) -> List[MediaItem]:
        now = self._clock()
        key = (text.lower(), self.library_only)
        self._searches = {k: v for k, v in self._searches.items() if now - v[0] < SEARCH_TTL}
        if key in self._searches:
            return self._searches[key][1]
        args: Dict[str, Any] = {"search_query": text, "media_types": list(SEARCH_TYPES), "limit": limit}
        if self.library_only:
            args["providers"] = ["library"]
        raw = await self.call("music/search", **args) or {}
        items = [MediaItem.from_dict(item) for result_key in SEARCH_KEYS
                 for item in raw.get(result_key) or [] if isinstance(item, dict)]
        self._searches[key] = (now, items)
        return items

    async def recently_played(self, limit: int = 8) -> List[MediaItem]:
        return _items(await self.call("music/recently_played_items", limit=limit))

    async def in_progress(self, limit: int = 3) -> List[MediaItem]:
        return _items(await self.call("music/in_progress_items", limit=limit))

    async def library(
        self, kind: str, search: str = "", limit: int = 50, favorite: Optional[bool] = None
    ) -> List[MediaItem]:
        args: Dict[str, Any] = {"limit": limit}
        if search:
            args["search"] = search
        if favorite is not None:
            args["favorite"] = favorite
        items = _items(await self.call(f"music/{LIBRARY_COMMANDS[kind]}/library_items", **args))
        return sorted(items, key=lambda item: not item.favorite)

    async def favorites(self, search: str = "", per_kind: int = 10) -> List[MediaItem]:
        lists = await asyncio.gather(
            *(self.library(kind, search, per_kind, favorite=True) for kind in LIBRARY_COMMANDS)
        )
        return [item for items in lists for item in items]

    async def podcast_episodes(self, podcast: MediaItem) -> List[MediaItem]:
        raw = await self.call(
            "music/podcasts/podcast_episodes",
            item_id=podcast.item_id,
            provider_instance_id_or_domain=podcast.provider,
        )
        return sorted(_items(raw), key=lambda episode: (episode.release_date or "", episode.position), reverse=True)

    async def play_media(self, queue_id: str, uri: str, option: str = "play", radio: bool = False) -> None:
        args: Dict[str, Any] = {"queue_id": queue_id, "media": uri, "option": option}
        if radio:
            args["radio_mode"] = True
        await self.call("player_queues/play_media", **args)
        self.invalidate_players()

    async def player_cmd(self, player_id: str, command: str, **args: Any) -> None:
        await self.call(f"players/cmd/{command}", player_id=player_id, **args)
        self.invalidate_players()

    async def aclose(self) -> None:
        await self._http.aclose()
