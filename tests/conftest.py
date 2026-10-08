import asyncio

import pytest

import app
from client import ServerError
import musicassistant
from models import MediaItem, NowPlaying, Player

KITCHEN = Player("kitchen", "Kitchen", state="playing", volume=35, muted=False,
                 now_playing=NowPlaying("One More Time", "Daft Punk", "Discovery",
                                        "/imageproxy/abc?size=256", 320, 133))
OFFICE = Player("office", "Office", state="idle", volume=20)
DOWNSTAIRS = Player("downstairs", "Downstairs", type="group", state="paused", volume=50)
TRACK = MediaItem("1", "library", "One More Time", "library://track/1", "track",
                  artists=("Daft Punk",), album="Discovery")
ARTIST = MediaItem("2", "library", "Daft Punk", "library://artist/2", "artist")
PODCAST = MediaItem("3", "library", "The Daily", "library://podcast/3", "podcast", publisher="NYT")
EPISODE = MediaItem("4", "library", "Monday", "library://podcast_episode/4", "podcast_episode",
                    duration=2880, resume_position_ms=1680000, release_date="2026-09-12T05:00:00+00:00")
BOOK = MediaItem("5", "library", "Dune", "library://audiobook/5", "audiobook",
                 authors=("Frank Herbert",), duration=75600, resume_position_ms=10800000)
STATION = MediaItem("6", "library", "Radio Paradise", "library://radio/6", "radio")
BASE = "http://ma.local:8095"


class FakeClient:
    base_url = BASE

    def __init__(self):
        self.players_list = [KITCHEN, OFFICE, DOWNSTAIRS]
        self.search_items = []
        self.recents = []
        self.progress = []
        self.library_items = {}
        self.episodes = []
        self.calls = []
        self.error = None
        self.failing = set()
        self.closed = False

    async def _record(self, *call):
        self.calls.append(call)
        if self.error:
            raise self.error
        if call[0] in self.failing:
            raise ServerError(f"{call[0]} failed")

    async def players(self):
        await self._record("players")
        return self.players_list

    async def search(self, text, limit=5):
        await self._record("search", text)
        return self.search_items

    async def recently_played(self, limit=8):
        await self._record("recently_played")
        return self.recents

    async def in_progress(self, limit=3):
        await self._record("in_progress")
        return self.progress

    async def library(self, kind, search="", limit=50, favorite=None):
        await self._record("library", kind, search)
        return self.library_items.get(kind, [])

    async def favorites(self, search="", per_kind=10):
        await self._record("favorites", search)
        return self.library_items.get("favorites", [])

    async def podcast_episodes(self, podcast):
        await self._record("podcast_episodes", podcast.item_id)
        return self.episodes

    async def play_media(self, queue_id, uri, option="play", radio=False):
        await self._record("play_media", queue_id, uri, option, radio)

    async def player_cmd(self, player_id, command, **args):
        await self._record("player_cmd", player_id, command, args)

    async def aclose(self):
        self.closed = True


@pytest.fixture
def fake(monkeypatch, tmp_path):
    client = FakeClient()
    monkeypatch.setattr(app, "session", app.Session(factory=lambda url, token, library_only=False: client))
    monkeypatch.setattr(app, "active_store", app.ActivePlayerStore(lambda: str(tmp_path)))
    monkeypatch.setattr(app, "podcasts_seen", {})
    launcher = app.plugin.launcher
    monkeypatch.setattr(launcher, "_settings", {"server_url": BASE, "token": "secret"})
    monkeypatch.setattr(launcher, "action_keyword", "ma")
    return client


@pytest.fixture
def messages(monkeypatch):
    sent = []

    async def invoke(command):
        sent.append(command)

    monkeypatch.setattr(app.plugin.launcher.api, "invoke", invoke)
    return sent


def run_query(text):
    return asyncio.run(musicassistant.query(text))


def run(coro):
    return asyncio.run(coro)


def action(result):
    return result.json_rpc_action["Method"], result.json_rpc_action["Parameters"]
