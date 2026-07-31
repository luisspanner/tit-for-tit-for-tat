import hashlib
import json
from pathlib import Path


class DiskCache:
    """Persists (system_prompt, history) -> raw LLM response text as JSON on disk."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))


def cache_key(system_prompt: str, history: list[tuple[str, str]]) -> str:
    payload = json.dumps({"prompt": system_prompt, "history": history}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
