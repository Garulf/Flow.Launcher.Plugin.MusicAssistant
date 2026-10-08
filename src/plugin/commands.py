import re
from dataclasses import dataclass
from typing import Optional, Union

TRANSPORT_VERBS = {
    "play": "play",
    "pause": "pause",
    "stop": "stop",
    "next": "next",
    "prev": "previous",
    "previous": "previous",
}
LIBRARY_VERBS = {
    "playlists": "playlists",
    "radio": "radio",
    "albums": "albums",
    "artists": "artists",
    "tracks": "tracks",
    "audiobooks": "audiobooks",
    "podcasts": "podcasts",
    "favorites": "favorites",
    "favourites": "favorites",
}
PLAYER_VERBS = {"players", "player"}
VOLUME_VERBS = {"vol", "volume"}


@dataclass(frozen=True)
class Dashboard:
    pass


@dataclass(frozen=True)
class Search:
    text: str


@dataclass(frozen=True)
class Players:
    filter: str = ""


@dataclass(frozen=True)
class Transport:
    command: str


@dataclass(frozen=True)
class Volume:
    level: Optional[int] = None
    delta: Optional[int] = None


@dataclass(frozen=True)
class Mute:
    pass


@dataclass(frozen=True)
class Library:
    kind: str
    filter: str = ""


@dataclass(frozen=True)
class Episodes:
    podcast: str


Route = Union[Dashboard, Search, Players, Transport, Volume, Mute, Library, Episodes]


def parse(text: str) -> Route:
    text = text.strip()
    if not text:
        return Dashboard()
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        quoted = text[1:-1].strip()
        return Search(quoted) if quoted else Dashboard()
    verb, _, rest = text.partition(" ")
    verb, rest = verb.lower(), rest.strip()
    if verb in PLAYER_VERBS:
        return Players(rest)
    if verb in LIBRARY_VERBS:
        return Library(LIBRARY_VERBS[verb], rest)
    if verb == "podcast":
        return Episodes(rest) if rest else Library("podcasts")
    if verb in VOLUME_VERBS:
        volume = _volume(rest)
        if volume is not None:
            return volume
    elif not rest and verb in TRANSPORT_VERBS:
        return Transport(TRANSPORT_VERBS[verb])
    elif not rest and verb == "mute":
        return Mute()
    return Search(text)


def _volume(argument: str) -> Optional[Volume]:
    if not argument:
        return Volume()
    if re.fullmatch(r"[+-]\d{1,3}", argument):
        return Volume(delta=int(argument))
    if re.fullmatch(r"\d{1,3}", argument):
        return Volume(level=min(int(argument), 100))
    return None
