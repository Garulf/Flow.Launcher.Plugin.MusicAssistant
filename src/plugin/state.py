import json
from pathlib import Path
from typing import Callable, List, Optional

from models import Player

FILE_NAME = "state.json"


class ActivePlayerStore:
    def __init__(self, directory: Callable[[], Optional[str]]) -> None:
        self._directory = directory
        self._memory: Optional[str] = None

    def _path(self) -> Optional[Path]:
        directory = self._directory()
        return Path(directory) / FILE_NAME if directory else None

    def get(self) -> Optional[str]:
        path = self._path()
        if path is None:
            return self._memory
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._memory
        value = data.get("active_player") if isinstance(data, dict) else None
        return value if isinstance(value, str) else self._memory

    def set(self, player_id: str) -> None:
        self._memory = player_id
        path = self._path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"active_player": player_id}), encoding="utf-8")
        except OSError:
            pass


def choose_active(players: List[Player], stored_id: Optional[str]) -> Optional[Player]:
    available = [player for player in players if player.available]
    for player in available:
        if player.player_id == stored_id:
            return player
    for player in available:
        if player.playing:
            return player
    return available[0] if available else None
