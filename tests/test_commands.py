import pytest

from commands import (Dashboard, Episodes, Library, Mute, Players, Search, Transport, Volume,
                      parse)


@pytest.mark.parametrize("text, route", [
    ("", Dashboard()),
    ("   ", Dashboard()),
    ("daft punk", Search("daft punk")),
    ("  daft punk  ", Search("daft punk")),
    ('"next"', Search("next")),
    ('""', Dashboard()),
    ("players", Players("")),
    ("player kit", Players("kit")),
    ("Players  Living Room", Players("Living Room")),
    ("play", Transport("play")),
    ("PAUSE", Transport("pause")),
    ("stop", Transport("stop")),
    ("next", Transport("next")),
    ("prev", Transport("previous")),
    ("previous", Transport("previous")),
    ("next to me", Search("next to me")),
    ("play that funky music", Search("play that funky music")),
    ("mute", Mute()),
    ("mute city", Search("mute city")),
    ("vol", Volume()),
    ("volume", Volume()),
    ("vol 40", Volume(level=40)),
    ("vol 250", Volume(level=100)),
    ("vol +5", Volume(delta=5)),
    ("vol -10", Volume(delta=-10)),
    ("vol loud", Search("vol loud")),
    ("playlists", Library("playlists")),
    ("radio jazz", Library("radio", "jazz")),
    ("albums discovery", Library("albums", "discovery")),
    ("artists", Library("artists")),
    ("tracks", Library("tracks")),
    ("audiobooks", Library("audiobooks")),
    ("podcasts", Library("podcasts")),
    ("favorites", Library("favorites")),
    ("favourites rock", Library("favorites", "rock")),
    ("podcast", Library("podcasts")),
    ("podcast The Daily", Episodes("The Daily")),
])
def test_parse(text, route):
    assert parse(text) == route
