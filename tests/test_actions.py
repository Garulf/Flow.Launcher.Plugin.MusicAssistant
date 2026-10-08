import actions
import app
from client import ServerError
from conftest import EPISODE, run
from launcher import KEEP_OPEN


def test_play_media_calls_client(fake, messages):
    run(actions.play_media("kitchen", "Kitchen", "library://track/1", "next", False))
    assert fake.calls == [("play_media", "kitchen", "library://track/1", "next", False)]
    assert messages == []


def test_failure_shows_message(fake, messages):
    fake.error = ServerError("Queue kitchen is not available")
    run(actions.play_media("kitchen", "Kitchen", "library://track/1"))
    (command,) = messages
    assert command["Method"] == "Flow.Launcher.ShowMsg"
    assert command["Parameters"][:2] == ["Couldn't play on Kitchen", "Queue kitchen is not available"]


def test_player_cmd_failure_wording(fake, messages):
    fake.error = ServerError("boom")
    run(actions.player_cmd("kitchen", "Kitchen", "next"))
    assert messages[0]["Parameters"][0] == "Couldn't skip to the next track on Kitchen"


def test_set_volume_and_mute(fake, messages):
    run(actions.set_volume("kitchen", "Kitchen", 40))
    run(actions.set_mute("kitchen", "Kitchen", True))
    assert fake.calls == [
        ("player_cmd", "kitchen", "volume_set", {"volume_level": 40}),
        ("player_cmd", "kitchen", "volume_mute", {"muted": True}),
    ]


def test_play_latest_episode(fake, messages):
    fake.episodes = [EPISODE]
    run(actions.play_latest_episode("kitchen", "Kitchen", "3", "library", "The Daily"))
    assert fake.calls[-1] == ("play_media", "kitchen", EPISODE.uri, "play", False)


def test_play_latest_episode_without_episodes(fake, messages):
    run(actions.play_latest_episode("kitchen", "Kitchen", "3", "library", "The Daily"))
    assert messages[0]["Parameters"][:2] == ["Couldn't play on Kitchen", "The Daily has no episodes"]


def test_set_active_stores_and_returns_to_dashboard(fake, messages):
    assert run(actions.set_active("office")) == KEEP_OPEN
    assert app.active_store.get() == "office"
    assert messages[0]["Method"] == "Flow.Launcher.ChangeQuery"
    assert messages[0]["Parameters"][0] == "ma "


def test_open_settings(fake, messages):
    run(actions.open_settings())
    assert messages[0]["Method"] == "Flow.Launcher.OpenSettingDialog"


def test_keep_open():
    assert run(actions.keep_open()) == KEEP_OPEN


def test_unexpected_failure_shows_message(fake, messages):
    fake.error = RuntimeError("boom")
    run(actions.player_cmd("kitchen", "Kitchen", "next"))
    assert messages[0]["Parameters"][:2] == ["Couldn't skip to the next track on Kitchen", "boom"]
