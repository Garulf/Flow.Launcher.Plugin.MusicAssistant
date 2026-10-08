from models import Player
from state import ActivePlayerStore, choose_active

KITCHEN = Player("kitchen", "Kitchen", state="idle")
OFFICE = Player("office", "Office", state="playing")
GONE = Player("gone", "Gone", available=False, state="playing")


def test_choose_active_prefers_stored():
    assert choose_active([KITCHEN, OFFICE], "kitchen") is KITCHEN


def test_choose_active_falls_back_to_playing_when_stored_missing():
    assert choose_active([KITCHEN, OFFICE], "nope") is OFFICE


def test_choose_active_skips_unavailable_stored_and_playing():
    assert choose_active([GONE, KITCHEN], "gone") is KITCHEN


def test_choose_active_first_available():
    assert choose_active([GONE, KITCHEN], None) is KITCHEN


def test_choose_active_none():
    assert choose_active([GONE], None) is None
    assert choose_active([], "x") is None


def test_store_round_trip(tmp_path):
    store = ActivePlayerStore(lambda: str(tmp_path / "settings"))
    assert store.get() is None
    store.set("kitchen")
    assert ActivePlayerStore(lambda: str(tmp_path / "settings")).get() == "kitchen"


def test_store_without_directory_keeps_value_in_memory():
    store = ActivePlayerStore(lambda: None)
    store.set("office")
    assert store.get() == "office"


def test_store_ignores_corrupt_file(tmp_path):
    (tmp_path / "state.json").write_text("{nope", encoding="utf-8")
    assert ActivePlayerStore(lambda: str(tmp_path)).get() is None
