import app
from client import AuthFailed, ServerError
from conftest import ARTIST, BOOK, EPISODE, PODCAST, STATION, TRACK, action, run_query
from models import Player


def titles(results):
    return [r.title for r in results]


def test_every_result_has_an_action_and_descending_scores(fake):
    fake.recents = [TRACK]
    results = run_query("")
    assert all(r.json_rpc_action for r in results)
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    assert len({r.score for r in results}) == len(results)


def test_dashboard(fake):
    fake.progress = [EPISODE, BOOK]
    fake.recents = [TRACK, STATION]
    results = run_query("")
    assert titles(results) == [
        "One More Time", "Monday", "Dune", "One More Time", "Radio Paradise",
    ]
    assert results[1].subtitle == "Continue listening · 12 Sep 2026 · 48 min · 20 min left"


def test_dashboard_uses_stored_active_player(fake):
    app.active_store.set("office")
    assert run_query("")[0].title == "Nothing playing on Office"


def test_no_players(fake):
    fake.players_list = [Player("x", "X", available=False)]
    (result,) = run_query("")
    assert result.title == "No players available"


def test_not_configured(fake, monkeypatch):
    monkeypatch.setattr(app.plugin.launcher, "_settings", {"server_url": "", "token": ""})
    (result,) = run_query("daft punk")
    assert result.title == "Set up Music Assistant"
    assert action(result)[0] == "open_settings"


def test_auth_failure(fake):
    fake.error = AuthFailed("Authentication failed")
    (result,) = run_query("")
    assert result.title == "Music Assistant rejected the token"


def test_server_error(fake):
    fake.error = ServerError("Internal server error")
    (result,) = run_query("x")
    assert (result.title, result.subtitle) == ("Music Assistant error", "Internal server error")


def test_search_orders_exact_match_first(fake):
    fake.search_items = [TRACK, ARTIST]
    results = run_query("daft punk")
    assert titles(results) == ["Daft Punk", "One More Time"]
    assert ("search", "daft punk") in fake.calls


def test_quoted_search(fake):
    fake.search_items = [TRACK]
    run_query('"next"')
    assert ("search", "next") in fake.calls


def test_search_no_results(fake):
    (result,) = run_query("zzz")
    assert result.title == 'No results for "zzz"'


def test_players_view(fake):
    results = run_query("players")
    assert titles(results) == ["Kitchen", "Downstairs", "Office"]
    assert results[0].subtitle.startswith("Active")


def test_players_filter(fake):
    assert titles(run_query("players off")) == ["Office"]
    (empty,) = run_query("players zzz")
    assert empty.title == 'No players match "zzz"'


def test_transport_verb(fake):
    (result,) = run_query("next")
    assert action(result) == ("player_cmd", ["kitchen", "Kitchen", "next"])


def test_volume_views(fake):
    assert titles(run_query("vol")) == ["Volume 35%", "Volume up", "Volume down"]
    (set_to,) = run_query("vol 40")
    assert set_to.title == "Set Kitchen volume to 40%"
    assert action(set_to) == ("set_volume", ["kitchen", "Kitchen", 40])
    (step,) = run_query("vol +80")
    assert action(step)[1][2] == 100
    (down,) = run_query("vol -50")
    assert action(down)[1][2] == 0


def test_volume_up_down_rows(fake):
    _, up, down = run_query("vol")
    assert action(up) == ("player_cmd", ["kitchen", "Kitchen", "volume_up"])
    assert action(down) == ("player_cmd", ["kitchen", "Kitchen", "volume_down"])


def test_mute_toggle(fake):
    (result,) = run_query("mute")
    assert result.title == "Mute Kitchen"
    assert action(result) == ("set_mute", ["kitchen", "Kitchen", True])
    fake.players_list = [Player("kitchen", "Kitchen", muted=True)]
    assert run_query("mute")[0].title == "Unmute Kitchen"


def test_library_view(fake):
    fake.library_items["playlists"] = [TRACK]
    assert titles(run_query("playlists chill")) == ["One More Time"]
    assert ("library", "playlists", "chill") in fake.calls


def test_library_empty_messages(fake):
    assert run_query("albums")[0].title == "No albums in your library"
    assert run_query("albums zzz")[0].title == 'No results for "zzz"'


def test_favorites(fake):
    fake.library_items["favorites"] = [ARTIST]
    assert titles(run_query("favorites")) == ["Daft Punk"]
    assert ("favorites", "") in fake.calls


def test_podcasts_then_episodes_from_seen(fake):
    fake.library_items["podcasts"] = [PODCAST]
    fake.episodes = [EPISODE]
    (podcast,) = run_query("podcasts")
    assert action(podcast) == ("change_query", ["ma podcast The Daily"])
    fake.library_items["podcasts"] = []
    results = run_query("podcast the daily")
    assert titles(results) == ["Monday"]
    assert ("podcast_episodes", "3") in fake.calls


def test_episodes_resolve_from_library(fake):
    fake.library_items["podcasts"] = [PODCAST]
    fake.episodes = [EPISODE]
    assert titles(run_query("podcast The Daily")) == ["Monday"]


def test_unknown_podcast(fake):
    (result,) = run_query("podcast Nope")
    assert result.title == 'No podcast named "Nope"'


def test_podcast_without_episodes(fake):
    fake.library_items["podcasts"] = [PODCAST]
    (result,) = run_query("podcast The Daily")
    assert result.title == "The Daily has no episodes"


def test_search_results_remember_podcasts(fake):
    fake.search_items = [PODCAST]
    run_query("daily")
    assert app.podcasts_seen["the daily"] == PODCAST


def test_unexpected_error_still_returns_a_result(fake):
    fake.error = RuntimeError("boom")
    (result,) = run_query("x")
    assert result.title == "Music Assistant error"
    assert result.subtitle == "boom"


def test_scores_leave_room_for_flow_selection_boost(fake):
    fake.recents = [TRACK]
    scores = [r.score for r in run_query("")]
    assert all(a - b >= 1000 for a, b in zip(scores, scores[1:]))


def test_dashboard_survives_failing_secondary_calls(fake):
    fake.failing = {"in_progress"}
    fake.recents = [TRACK]
    assert titles(run_query("")) == ["One More Time", "One More Time"]


def test_episode_list_is_capped(fake):
    fake.library_items["podcasts"] = [PODCAST]
    fake.episodes = [EPISODE] * 60
    assert len(run_query("podcast The Daily")) == 50
