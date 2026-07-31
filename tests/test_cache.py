from pathlib import Path

from tournament.cache import DiskCache, cache_key


def test_cache_get_returns_none_when_missing(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path / "cache.json")
    assert cache.get("missing") is None


def test_cache_set_then_get(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path / "cache.json")
    cache.set("key", "D")
    assert cache.get("key") == "D"


def test_cache_persists_to_disk_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    DiskCache(path).set("key", "C")

    reloaded = DiskCache(path)
    assert reloaded.get("key") == "C"


def test_cache_key_is_deterministic_and_sensitive_to_inputs() -> None:
    key_a = cache_key("prompt", [("C", "D")])
    key_b = cache_key("prompt", [("C", "D")])
    key_c = cache_key("prompt", [("D", "D")])
    key_d = cache_key("other prompt", [("C", "D")])

    assert key_a == key_b
    assert key_a != key_c
    assert key_a != key_d
