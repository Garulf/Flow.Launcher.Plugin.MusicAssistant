import asyncio

from pyflowlauncher.jsonrpc import JsonRPCV2Client

from launcher import KEEP_OPEN, MALauncher


def drain(launcher):
    async def collect():
        return [request async for request in launcher._client.messages()]

    return asyncio.run(collect())


def feed(monkeypatch, requests):
    async def messages(self):
        for request in requests:
            yield request

    monkeypatch.setattr(JsonRPCV2Client, "messages", messages)


def test_keep_open_reply_is_sent_as_is():
    launcher = MALauncher()
    sent = []
    launcher._client.send = sent.append
    launcher._send_response(7, "change_query", KEEP_OPEN)
    launcher._send_response(8, "play_media", None)
    assert sent == [
        {"id": 7, "result": {"hide": False}, "error": None},
        {"id": 8, "result": {}, "error": None},
    ]


def test_action_keyword_is_tracked(monkeypatch):
    requests = [{"id": 1, "method": "query", "params": [{"search": "x", "actionKeyword": "ma"}, {}]}]
    feed(monkeypatch, requests)
    launcher = MALauncher()
    assert drain(launcher) == requests
    assert launcher.action_keyword == "ma"


def test_settings_dir_is_read_from_initialize(monkeypatch):
    metadata = {"pluginSettingsDirectoryPath": r"C:\Flow\Settings\Plugins\Music Assistant"}
    feed(monkeypatch, [{"id": 0, "method": "initialize", "params": [{"currentPluginMetadata": metadata}]}])
    launcher = MALauncher()
    drain(launcher)
    assert launcher.settings_dir == r"C:\Flow\Settings\Plugins\Music Assistant"


def test_settings_dir_defaults_to_none(monkeypatch):
    feed(monkeypatch, [{"id": 0, "method": "initialize", "params": [{}]}])
    launcher = MALauncher()
    drain(launcher)
    assert launcher.settings_dir is None
