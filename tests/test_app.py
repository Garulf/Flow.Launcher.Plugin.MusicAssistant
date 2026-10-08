import asyncio

import pytest

import app
from client import NotConfigured


def test_session_requires_url_and_token():
    with pytest.raises(NotConfigured, match="Add your server URL and token"):
        app.Session(factory=lambda *a, **k: object()).client({"server_url": "http://x", "token": " "})


def test_session_reuses_client_for_same_settings():
    made = []

    def factory(url, token, library_only=False):
        made.append((url, token, library_only))
        return object()

    session = app.Session(factory=factory)
    settings = {"server_url": "http://x", "token": "t", "library_only": "false"}
    assert session.client(settings) is session.client(dict(settings))
    assert made == [("http://x", "t", False)]


def test_session_rebuilds_client_on_settings_change(monkeypatch):
    monkeypatch.setattr(app, "RETIRE_AFTER", 0)

    class Client:
        def __init__(self, *args, **kwargs):
            self.closed = False

        async def aclose(self):
            self.closed = True

    session = app.Session(factory=Client)

    async def go():
        old = session.client({"server_url": "http://x", "token": "a"})
        new = session.client({"server_url": "http://x", "token": "b", "library_only": True})
        assert not old.closed
        await asyncio.sleep(0.01)
        return old, new

    old, new = asyncio.run(go())
    assert old is not new and old.closed and not new.closed


def test_is_enabled():
    assert app.is_enabled(True) and app.is_enabled("True")
    assert not app.is_enabled(False) and not app.is_enabled("false") and not app.is_enabled(None)
