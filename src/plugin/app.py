import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple

from pyflowlauncher import Plugin

from client import MAClient, NotConfigured
from launcher import MALauncher
from models import MediaItem
from state import ActivePlayerStore

ROOT = Path(__file__).resolve().parent.parent
ICON = str(ROOT / "icon.png")
RETIRE_AFTER = 30.0

plugin = Plugin(launcher=MALauncher())


def icon(name: str) -> str:
    return str(ROOT / "icons" / f"{name}.png")


def full_query(text: str) -> str:
    keyword = plugin.launcher.action_keyword
    return f"{keyword} {text}" if keyword else text


def is_enabled(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


class Session:
    """Owns the MAClient for the current settings; a replaced client is closed after a grace period."""

    def __init__(self, factory: Callable[..., MAClient] = MAClient) -> None:
        self._factory = factory
        self._key: Optional[Tuple[str, str, bool]] = None
        self._client: Optional[MAClient] = None
        self._retiring: Set[asyncio.Task] = set()

    def client(self, settings: Dict[str, Any]) -> MAClient:
        url = str(settings.get("server_url") or "").strip()
        token = str(settings.get("token") or "").strip()
        if not url or not token:
            raise NotConfigured("Add your server URL and token")
        key = (url, token, is_enabled(settings.get("library_only")))
        if key != self._key or self._client is None:
            client = self._factory(url, token, library_only=key[2])
            self._retire(self._client)
            self._key, self._client = key, client
        return self._client

    def _retire(self, client: Optional[MAClient]) -> None:
        if client is None:
            return

        async def close_later() -> None:
            await asyncio.sleep(RETIRE_AFTER)
            await client.aclose()

        try:
            task = asyncio.get_running_loop().create_task(close_later())
        except RuntimeError:
            return
        self._retiring.add(task)
        task.add_done_callback(self._retiring.discard)


session = Session()
active_store = ActivePlayerStore(lambda: plugin.launcher.settings_dir)
podcasts_seen: Dict[str, MediaItem] = {}
