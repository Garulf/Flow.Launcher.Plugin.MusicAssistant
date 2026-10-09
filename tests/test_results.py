import pytest

import app
import results as r
from client import AuthFailed, NotConfigured, ServerError, Unreachable
from conftest import (ARTIST, BASE, BOOK, DOWNSTAIRS, EPISODE, KITCHEN, OFFICE, PODCAST, STATION,
                      TRACK, action)
from models import Image, MediaItem, Player

TARGET = r.Target(BASE, KITCHEN, (OFFICE, DOWNSTAIRS))


def titles(results):
    return [result.title for result in results]


@pytest.mark.parametrize("seconds, text", [(0, "0:00"), (65, "1:05"), (3725, "1:02:05")])
def test_clock(seconds, text):
    assert r.clock(seconds) == text


@pytest.mark.parametrize("seconds, text", [(59, "1 min"), (2880, "48 min"), (25920, "7 h 12 min"), (7200, "2 h")])
def test_long_duration(seconds, text):
    assert r.long_duration(seconds) == text


def test_subtitles_per_type():
    assert r.media_subtitle(TRACK) == "Track · Daft Punk · Discovery"
    assert r.media_subtitle(ARTIST) == "Artist"
    assert r.media_subtitle(PODCAST) == "Podcast · NYT"
    assert r.media_subtitle(STATION) == "Radio"
    assert r.media_subtitle(BOOK) == "Audiobook · Frank Herbert · 21 h · 18 h left"
    assert r.media_subtitle(EPISODE) == "12 Sep 2026 · 48 min · 20 min left"


def test_subtitles_with_missing_fields():
    bare_episode = MediaItem("e", "x", "E", "x://podcast_episode/e", "podcast_episode")
    assert r.media_subtitle(bare_episode) == "Episode"
    odd = MediaItem("g", "x", "G", "x://genre/g", "genre")
    assert r.media_subtitle(odd) == "Genre"
    bad_date = MediaItem("e", "x", "E", "u", "podcast_episode", release_date="soon", duration=60)
    assert r.media_subtitle(bad_date) == "1 min"
    finished = MediaItem("b", "x", "B", "u", "audiobook", duration=3600, resume_position_ms=0, fully_played=True)
    assert r.media_subtitle(finished) == "Audiobook · 1 h"


def test_media_result_plays_on_active_player_with_art():
    item = MediaItem("1", "library", "T", "library://track/1", "track", image=Image("/x", proxy_id="p" * 64))
    result = r.media_result(item, TARGET)
    assert action(result) == ("play_media", ["kitchen", "Kitchen", "library://track/1", "play", False])
    assert result.icon == f"{BASE}/imageproxy/{'p' * 64}?size=256"


def test_media_result_without_art_uses_type_icon():
    assert r.media_result(STATION, TARGET).icon == app.icon("radio")
    assert r.media_result(TRACK, TARGET).icon == app.icon("music")


def test_track_menu():
    menu = r.media_menu(TRACK, TARGET)
    assert titles(menu) == ["Play now", "Play next", "Add to queue", "Start radio", "Play on Office", "Play on Downstairs"]
    assert action(menu[1])[1] == ["kitchen", "Kitchen", "library://track/1", "next", False]
    assert action(menu[2])[1][3] == "add"
    assert action(menu[3])[1] == ["kitchen", "Kitchen", "library://track/1", "play", True]
    assert action(menu[5])[1] == ["downstairs", "Downstairs", "library://track/1", "play", False]


def test_media_result_carries_menu_as_context_data():
    result = r.media_result(TRACK, TARGET)
    assert titles(result.context_data) == titles(r.media_menu(TRACK, TARGET))


def test_radio_and_book_menus_have_no_start_radio():
    assert "Start radio" not in titles(r.media_menu(STATION, TARGET))
    assert "Start radio" not in titles(r.media_menu(BOOK, TARGET))


def test_podcast_opens_episodes_and_menu_offers_latest(fake):
    result = r.media_result(PODCAST, TARGET)
    assert action(result) == ("change_query", ["ma podcast The Daily"])
    menu = r.media_menu(PODCAST, TARGET)
    assert titles(menu)[0] == "Play latest episode"
    assert action(menu[0]) == ("play_latest_episode", ["kitchen", "Kitchen", "3", "library", "The Daily"])
    assert "Start radio" not in titles(menu)


def test_media_result_custom_subtitle():
    assert r.media_result(EPISODE, TARGET, subtitle="Continue listening · Episode").subtitle == "Continue listening · Episode"


def test_now_playing_result():
    result = r.now_playing_result(TARGET)
    assert result.title == "One More Time"
    assert result.subtitle == "Daft Punk · Kitchen · 2:13 / 5:20"
    assert result.icon == f"{BASE}/imageproxy/abc?size=256"
    assert action(result) == ("player_cmd", ["kitchen", "Kitchen", "play_pause"])


def test_now_playing_menu_has_controls_and_volume(fake):
    result = r.now_playing_result(TARGET)
    menu = result.context_data
    assert titles(menu) == [
        "Pause on Kitchen", "Next track on Kitchen", "Previous track on Kitchen", "Stop on Kitchen",
        "Volume 35%", "Volume up", "Volume down", "Mute Kitchen",
    ]
    assert action(menu[0]) == ("player_cmd", ["kitchen", "Kitchen", "pause"])
    assert action(menu[4]) == ("change_query", ["ma vol "])
    assert action(menu[5]) == ("player_cmd", ["kitchen", "Kitchen", "volume_up"])
    assert action(menu[7]) == ("set_mute", ["kitchen", "Kitchen", True])


def test_now_playing_menu_when_paused_muted_or_idle(fake):
    paused = Player("p", "Den", state="paused", muted=True, now_playing=KITCHEN.now_playing)
    menu = r.now_playing_result(r.Target(BASE, paused, ())).context_data
    assert titles(menu)[0] == "Play on Den"
    assert titles(menu)[-1] == "Unmute Den"
    idle = r.now_playing_result(r.Target(BASE, OFFICE, ()))
    assert titles(idle.context_data) == titles(r.now_playing_menu(OFFICE))
    assert titles(idle.context_data)[0] == "Play on Office"


def test_now_playing_paused_and_idle():
    paused = Player("p", "Den", state="paused", now_playing=KITCHEN.now_playing)
    assert r.now_playing_result(r.Target(BASE, paused, ())).subtitle.startswith("Paused · Daft Punk · Den")
    idle = r.now_playing_result(r.Target(BASE, OFFICE, ()))
    assert idle.title == "Nothing playing on Office"
    assert idle.icon == app.icon("music")


def test_player_result_marks_active_and_state():
    result = r.player_result(KITCHEN, "kitchen")
    assert result.subtitle == "Active · Playing · One More Time · Daft Punk"
    assert action(result) == ("set_active", ["kitchen"])
    assert result.icon == app.icon("speaker")
    assert r.player_result(DOWNSTAIRS, "kitchen").subtitle == "Paused"
    assert r.player_result(DOWNSTAIRS, "kitchen").icon == app.icon("group")


def test_transport_result():
    result = r.transport_result(KITCHEN, "next")
    assert result.title == "Next track on Kitchen"
    assert action(result) == ("player_cmd", ["kitchen", "Kitchen", "next"])


def test_volume_rows(fake):
    row = r.volume_row(KITCHEN)
    assert row.title == "Volume 35%"
    assert action(row) == ("change_query", ["ma vol "])
    unknown = r.volume_row(Player("x", "X"), keyword_row=True)
    assert unknown.title == "Volume unknown"
    assert action(unknown)[0] == "keep_open"


def test_switch_player_result(fake):
    result = r.switch_player_result(KITCHEN)
    assert result.title == "Player: Kitchen"
    assert action(result) == ("change_query", ["ma players "])


@pytest.mark.parametrize("error, title, method", [
    (NotConfigured("Add your server URL and token"), "Set up Music Assistant", "open_settings"),
    (AuthFailed("nope"), "Music Assistant rejected the token", "open_settings"),
    (Unreachable("Connection refused"), f"Can't reach {BASE}", "keep_open"),
    (ServerError("Invalid Command: x"), "Music Assistant error", "keep_open"),
])
def test_error_result(error, title, method):
    result = r.error_result(error, BASE)
    assert result.title == title
    assert action(result)[0] == method


def test_error_subtitles():
    assert r.error_result(NotConfigured("Add your server URL and token"), "").subtitle == "Add your server URL and token"
    assert r.error_result(Unreachable("Connection refused"), BASE).subtitle == "Connection refused"
    assert r.error_result(Unreachable("x"), "").title == "Can't reach Music Assistant"


def test_order_search_puts_exact_name_first():
    items = [TRACK, ARTIST]
    assert r.order_search(items, "daft punk") == [ARTIST, TRACK]
