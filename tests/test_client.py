import asyncio
import json

import httpx
import pytest

from client import AuthFailed, MAClient, NotConfigured, ServerError, Unreachable, normalize_url
from models import MediaItem

BASE = "http://ma.local:8095"
API = f"{BASE}/api"


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def run(coro):
    return asyncio.run(coro)


def client(**kwargs):
    return MAClient(BASE, "secret", **kwargs)


def sent(request):
    return json.loads(request.content)


@pytest.mark.parametrize("raw, url", [
    ("http://ma.local:8095", "http://ma.local:8095"),
    ("  http://ma.local:8095/  ", "http://ma.local:8095"),
    ("192.168.1.10:8095", "http://192.168.1.10:8095"),
    ("https://ma.example.com", "https://ma.example.com"),
])
def test_normalize_url(raw, url):
    assert normalize_url(raw) == url


def test_invalid_url_is_not_configured():
    with pytest.raises(NotConfigured):
        MAClient("http://[", "secret")


def test_call_sends_envelope_with_bearer(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json=[{"player_id": "a"}])
    result = run(client().call("players/all", return_unavailable=False))
    assert result == [{"player_id": "a"}]
    request = httpx_mock.get_request()
    assert request.headers["Authorization"] == "Bearer secret"
    body = sent(request)
    assert body["command"] == "players/all"
    assert body["args"] == {"return_unavailable": False}
    assert body["message_id"]


def test_empty_body_is_none(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", content=b"")
    assert run(client().call("players/cmd/play", player_id="a")) is None


def test_401_is_auth_failed(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", status_code=401, text="Authentication failed")
    with pytest.raises(AuthFailed):
        run(client().call("players/all"))


def test_error_status_is_server_error_with_text(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", status_code=400, text="Invalid Command: nope")
    with pytest.raises(ServerError, match="Invalid Command: nope"):
        run(client().call("nope"))


def test_connect_error_is_unreachable(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    with pytest.raises(Unreachable, match="Connection refused"):
        run(client().call("players/all"))


def test_timeout_is_unreachable(httpx_mock):
    httpx_mock.add_exception(httpx.ReadTimeout("timed out"))
    with pytest.raises(Unreachable, match="too long"):
        run(client().call("players/all"))


def test_invalid_json_is_server_error(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", text="<html>")
    with pytest.raises(ServerError):
        run(client().call("players/all"))


PLAYERS = [
    {"player_id": "kitchen", "name": "Kitchen", "playback_state": "playing"},
    {"player_id": "hidden", "name": "Hidden", "hide_in_ui": True},
]


def test_players_are_cached_briefly(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json=PLAYERS, is_reusable=True)
    clock = Clock()
    ma = client(clock=clock)

    async def go():
        first = await ma.players()
        await ma.players()
        clock.now = 5
        await ma.players()
        return first

    first = run(go())
    assert [p.player_id for p in first] == ["kitchen"]
    assert len(httpx_mock.get_requests()) == 2


def test_commands_invalidate_player_cache(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json=PLAYERS, is_reusable=True)
    ma = client(clock=Clock())

    async def go():
        await ma.players()
        await ma.player_cmd("kitchen", "next")
        await ma.players()

    run(go())
    commands = [sent(r)["command"] for r in httpx_mock.get_requests()]
    assert commands == ["players/all", "players/cmd/next", "players/all"]


def test_player_cmd_passes_extra_args(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", content=b"")
    run(client().player_cmd("kitchen", "volume_set", volume_level=40))
    assert sent(httpx_mock.get_request())["args"] == {"player_id": "kitchen", "volume_level": 40}


SEARCH = {
    "artists": [{"item_id": "1", "provider": "library", "name": "Daft Punk", "media_type": "artist"}],
    "tracks": [{"item_id": "2", "provider": "library", "name": "Around the World", "media_type": "track"}],
    "albums": [],
}


def test_search_flattens_in_type_order_and_memoizes(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json=SEARCH)
    clock = Clock()
    ma = client(clock=clock)

    async def go():
        items = await ma.search("Daft Punk")
        clock.now = 10
        again = await ma.search("daft punk")
        return items, again

    items, again = run(go())
    assert [i.media_type for i in items] == ["artist", "track"]
    assert again == items
    body = sent(httpx_mock.get_request())
    assert body["args"] == {
        "search_query": "Daft Punk",
        "media_types": ["artist", "album", "track", "playlist", "radio", "podcast", "audiobook"],
        "limit": 5,
    }


def test_search_memo_expires(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json=SEARCH, is_reusable=True)
    clock = Clock()
    ma = client(clock=clock)

    async def go():
        await ma.search("x")
        clock.now = 31
        await ma.search("x")

    run(go())
    assert len(httpx_mock.get_requests()) == 2


def test_library_only_search_restricts_providers(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json={})
    run(client(library_only=True).search("x"))
    assert sent(httpx_mock.get_request())["args"]["providers"] == ["library"]


def test_library_maps_radio_command_and_sorts_favorites_first(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json=[
        {"item_id": "1", "provider": "library", "name": "A", "media_type": "radio", "favorite": False},
        {"item_id": "2", "provider": "library", "name": "B", "media_type": "radio", "favorite": True},
    ])
    items = run(client().library("radio", "jazz"))
    assert [i.name for i in items] == ["B", "A"]
    body = sent(httpx_mock.get_request())
    assert body["command"] == "music/radios/library_items"
    assert body["args"] == {"limit": 50, "search": "jazz"}


def test_favorites_queries_every_kind(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json=[], is_reusable=True)
    run(client().favorites("rock"))
    commands = sorted(sent(r)["command"] for r in httpx_mock.get_requests())
    assert commands == sorted(f"music/{k}/library_items" for k in
                              ["playlists", "radios", "albums", "artists", "tracks", "audiobooks", "podcasts"])
    assert all(sent(r)["args"]["favorite"] is True for r in httpx_mock.get_requests())


def test_podcast_episodes_newest_first(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", json=[
        {"item_id": "1", "provider": "library", "name": "Old", "media_type": "podcast_episode",
         "metadata": {"release_date": "2026-01-01T00:00:00+00:00"}},
        {"item_id": "2", "provider": "library", "name": "New", "media_type": "podcast_episode",
         "metadata": {"release_date": "2026-09-01T00:00:00+00:00"}},
    ])
    podcast = MediaItem("9", "library", "Pod", "library://podcast/9", "podcast")
    episodes = run(client().podcast_episodes(podcast))
    assert [e.name for e in episodes] == ["New", "Old"]
    assert sent(httpx_mock.get_request())["args"] == {"item_id": "9", "provider_instance_id_or_domain": "library"}


def test_play_media_args(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", content=b"", is_reusable=True)

    async def go():
        ma = client()
        await ma.play_media("kitchen", "library://track/1")
        await ma.play_media("kitchen", "library://track/1", "next", radio=True)

    run(go())
    first, second = (sent(r)["args"] for r in httpx_mock.get_requests())
    assert first == {"queue_id": "kitchen", "media": "library://track/1", "option": "play"}
    assert second == {"queue_id": "kitchen", "media": "library://track/1", "option": "next", "radio_mode": True}


def test_recents_and_in_progress(httpx_mock):
    httpx_mock.add_response(url=API, method="POST",
                            json=[{"item_id": "1", "provider": "library", "name": "A", "media_type": "track"}],
                            is_reusable=True)

    async def go():
        ma = client()
        return await ma.recently_played(), await ma.in_progress()

    recents, progress = run(go())
    assert recents[0].name == "A" and progress[0].name == "A"
    first, second = (sent(r) for r in httpx_mock.get_requests())
    assert (first["command"], first["args"]) == ("music/recently_played_items", {"limit": 8})
    assert (second["command"], second["args"]) == ("music/in_progress_items", {"limit": 3})


@pytest.mark.parametrize("url", ["http://host:abc", "host:8095:1", "http://127.0.0.1:99999"])
def test_bad_port_is_not_configured(url):
    with pytest.raises(NotConfigured):
        MAClient(url, "secret")


def test_non_ascii_token_is_not_configured():
    with pytest.raises(NotConfigured, match="token"):
        MAClient(BASE, "tök")


def test_redirect_is_unreachable_and_names_the_target(httpx_mock):
    httpx_mock.add_response(url=API, method="POST", status_code=308,
                            headers={"Location": "https://ma.example.com/api"})
    with pytest.raises(Unreachable, match="https://ma.example.com/api"):
        run(client().call("players/all"))
