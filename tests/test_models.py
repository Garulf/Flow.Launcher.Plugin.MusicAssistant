from models import Image, MediaItem, Player, absolute_url, image_url

BASE = "http://ma.local:8095"
PROXY = "a" * 64


def test_image_url_prefers_remote_path():
    image = Image("https://i.scdn.co/image/x", remotely_accessible=True, proxy_id=PROXY)
    assert image_url(BASE, image) == "https://i.scdn.co/image/x"


def test_image_url_uses_proxy_id():
    assert image_url(BASE, Image("/music/cover.jpg", proxy_id=PROXY)) == f"{BASE}/imageproxy/{PROXY}?size=256"


def test_image_url_without_usable_source():
    assert image_url(BASE, Image("/music/cover.jpg")) is None
    assert image_url(BASE, None) is None


def test_absolute_url():
    assert absolute_url(BASE, "/imageproxy/x?size=256") == f"{BASE}/imageproxy/x?size=256"
    assert absolute_url(BASE, "https://cdn/x.jpg") == "https://cdn/x.jpg"
    assert absolute_url(BASE, "relative.jpg") is None
    assert absolute_url(BASE, None) is None


def test_track_from_dict():
    item = MediaItem.from_dict({
        "item_id": 12, "provider": "library", "name": "One More Time", "uri": "library://track/12",
        "media_type": "track", "favorite": True, "duration": 320,
        "artists": [{"name": "Daft Punk"}, {"name": "Romanthony"}],
        "album": {"name": "Discovery", "image": {"path": "/a.jpg", "proxy_id": PROXY}},
        "metadata": {"images": None},
    })
    assert item.item_id == "12"
    assert item.artists == ("Daft Punk", "Romanthony")
    assert item.album == "Discovery"
    assert item.favorite is True
    assert item.image == Image("/a.jpg", False, PROXY)


def test_thumb_preferred_over_other_images():
    item = MediaItem.from_dict({
        "item_id": "1", "provider": "library", "name": "x", "uri": "library://album/1", "media_type": "album",
        "metadata": {"images": [{"type": "fanart", "path": "/f.jpg", "proxy_id": "f"},
                                {"type": "thumb", "path": "/t.jpg", "proxy_id": "t"}]},
    })
    assert item.image.proxy_id == "t"


def test_media_item_minimal_mapping():
    item = MediaItem.from_dict({"item_id": "5", "provider": "spotify", "name": "Song", "media_type": "track"})
    assert item.uri == "spotify://track/5"
    assert item.artists == () and item.album is None and item.image is None


def test_audiobook_and_episode_fields():
    book = MediaItem.from_dict({
        "item_id": "b", "provider": "library", "name": "Dune", "uri": "library://audiobook/b",
        "media_type": "audiobook", "authors": ["Frank Herbert", {"name": "Someone"}],
        "duration": 7200, "resume_position_ms": 1800000, "fully_played": False,
    })
    assert book.authors == ("Frank Herbert", "Someone")
    assert book.resume_position_ms == 1800000
    episode = MediaItem.from_dict({
        "item_id": "e", "provider": "library", "name": "Ep 1", "uri": "library://podcast_episode/e",
        "media_type": "podcast_episode", "position": 3,
        "metadata": {"release_date": "2026-09-12T00:00:00+00:00"},
        "podcast": {"name": "Pod", "image": {"path": "/p.jpg", "proxy_id": "p"}},
    })
    assert episode.release_date == "2026-09-12T00:00:00+00:00"
    assert episode.position == 3
    assert episode.image.proxy_id == "p"


def test_player_from_dict_with_media():
    player = Player.from_dict({
        "player_id": "kitchen", "name": "Kitchen", "type": "player", "available": True,
        "playback_state": "playing", "volume_level": 35, "volume_muted": False,
        "current_media": {"uri": "x", "title": "One More Time", "artist": "Daft Punk",
                          "image_url": "/imageproxy/x", "duration": 320,
                          "elapsed_time": 100, "elapsed_time_last_updated": 1000.0},
    }, now=1010.0)
    assert player.playing
    assert player.volume == 35
    assert player.now_playing.title == "One More Time"
    assert player.now_playing.elapsed == 110


def test_paused_player_does_not_advance_elapsed():
    player = Player.from_dict({
        "player_id": "p", "name": "P", "playback_state": "paused",
        "current_media": {"uri": "x", "title": "T", "elapsed_time": 100, "elapsed_time_last_updated": 1000.0},
    }, now=1010.0)
    assert player.now_playing.elapsed == 100


def test_group_uses_group_volume():
    player = Player.from_dict({
        "player_id": "g", "name": "Downstairs", "type": "group", "volume_level": 10,
        "group_volume": 55, "group_volume_muted": True,
    }, now=0)
    assert player.is_group and player.volume == 55 and player.muted is True


def test_disabled_player_is_unavailable_and_media_without_title_is_ignored():
    player = Player.from_dict({"player_id": "x", "name": "X", "enabled": False,
                               "current_media": {"uri": "x"}}, now=0)
    assert not player.available
    assert player.now_playing is None
