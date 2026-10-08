from dataclasses import dataclass
from typing import Any, Optional, Tuple

IMAGE_SIZE = 256


@dataclass(frozen=True)
class Image:
    path: str
    remotely_accessible: bool = False
    proxy_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Any) -> Optional["Image"]:
        if not isinstance(data, dict) or not data.get("path"):
            return None
        return cls(data["path"], bool(data.get("remotely_accessible")), data.get("proxy_id"))


def image_url(base_url: str, image: Optional[Image]) -> Optional[str]:
    if image is None:
        return None
    if image.remotely_accessible and image.path.startswith(("http://", "https://")):
        return image.path
    if image.proxy_id:
        return f"{base_url}/imageproxy/{image.proxy_id}?size={IMAGE_SIZE}"
    return None


def absolute_url(base_url: str, url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("/"):
        return base_url + url
    return None


def _names(values: Any) -> Tuple[str, ...]:
    names = []
    for value in values or []:
        name = value.get("name") if isinstance(value, dict) else value
        if isinstance(name, str) and name:
            names.append(name)
    return tuple(names)


def _mapping(value: Any) -> Optional[dict]:
    return value if isinstance(value, dict) else None


def _thumb(data: Any) -> Optional[Image]:
    if not isinstance(data, dict):
        return None
    image = Image.from_dict(data.get("image"))
    if image:
        return image
    images = [i for i in (_mapping(data.get("metadata")) or {}).get("images") or [] if isinstance(i, dict)]
    thumbs = [i for i in images if i.get("type") == "thumb"]
    for candidate in thumbs + images:
        image = Image.from_dict(candidate)
        if image:
            return image
    return None


@dataclass(frozen=True)
class MediaItem:
    item_id: str
    provider: str
    name: str
    uri: str
    media_type: str
    artists: Tuple[str, ...] = ()
    album: Optional[str] = None
    owner: str = ""
    publisher: Optional[str] = None
    authors: Tuple[str, ...] = ()
    duration: int = 0
    resume_position_ms: Optional[int] = None
    fully_played: Optional[bool] = None
    favorite: bool = False
    release_date: Optional[str] = None
    position: int = 0
    image: Optional[Image] = None

    @classmethod
    def from_dict(cls, data: dict) -> "MediaItem":
        item_id = str(data.get("item_id", ""))
        provider = data.get("provider") or ""
        media_type = data.get("media_type") or ""
        album = _mapping(data.get("album"))
        podcast = _mapping(data.get("podcast"))
        return cls(
            item_id=item_id,
            provider=provider,
            name=data.get("name") or "",
            uri=data.get("uri") or f"{provider}://{media_type}/{item_id}",
            media_type=media_type,
            artists=_names(data.get("artists")),
            album=album.get("name") if album else None,
            owner=data.get("owner") or "",
            publisher=data.get("publisher"),
            authors=_names(data.get("authors")),
            duration=int(data.get("duration") or 0),
            resume_position_ms=data.get("resume_position_ms"),
            fully_played=data.get("fully_played"),
            favorite=bool(data.get("favorite")),
            release_date=(_mapping(data.get("metadata")) or {}).get("release_date"),
            position=int(data.get("position") or 0),
            image=_thumb(data) or _thumb(album) or _thumb(podcast),
        )


@dataclass(frozen=True)
class NowPlaying:
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    image_url: Optional[str] = None
    duration: Optional[int] = None
    elapsed: Optional[float] = None


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    type: str = "player"
    available: bool = True
    state: str = "idle"
    volume: Optional[int] = None
    muted: Optional[bool] = None
    now_playing: Optional[NowPlaying] = None

    @property
    def is_group(self) -> bool:
        return self.type == "group"

    @property
    def playing(self) -> bool:
        return self.state == "playing"

    @classmethod
    def from_dict(cls, data: dict, now: float) -> "Player":
        is_group = data.get("type") == "group"
        state = data.get("playback_state") or "idle"
        volume, muted = data.get("volume_level"), data.get("volume_muted")
        if is_group and data.get("group_volume") is not None:
            volume, muted = data.get("group_volume"), data.get("group_volume_muted")
        return cls(
            player_id=data["player_id"],
            name=data.get("name") or data["player_id"],
            type=data.get("type") or "player",
            available=bool(data.get("available", True)) and data.get("enabled", True) is not False,
            state=state,
            volume=volume,
            muted=muted,
            now_playing=_now_playing(data, state, now),
        )


def _now_playing(data: dict, state: str, now: float) -> Optional[NowPlaying]:
    media = _mapping(data.get("current_media"))
    if not media or not media.get("title"):
        return None
    elapsed = media.get("elapsed_time")
    updated = media.get("elapsed_time_last_updated")
    if elapsed is None:
        elapsed, updated = data.get("elapsed_time"), data.get("elapsed_time_last_updated")
    if elapsed is not None and updated is not None and state == "playing":
        elapsed += max(0.0, now - updated)
    return NowPlaying(
        title=media["title"],
        artist=media.get("artist"),
        album=media.get("album"),
        image_url=media.get("image_url"),
        duration=media.get("duration"),
        elapsed=elapsed,
    )
