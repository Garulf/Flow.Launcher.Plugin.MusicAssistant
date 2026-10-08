from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USED = {
    "play", "pause", "stop", "next", "previous", "queue", "volume", "mute", "speaker", "group",
    "music", "radio", "podcast", "audiobook", "warning", "settings",
}


def test_every_icon_the_plugin_uses_exists():
    missing = sorted(name for name in USED if not (ROOT / "data" / "icons" / f"{name}.png").exists())
    assert missing == []


def test_plugin_icon_exists():
    assert (ROOT / "data" / "icon.png").exists()
