import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "chatbot_config.json"

_cached_config: dict = {}
_last_mtime: float = 0.0


def load_config() -> dict:
    """
    Doc file chatbot_config.json co tu dong Hot-Reload theo mtime khi file thay doi tren dia
    (Ke thua co che hot-reload cua NCKH nhung khong tao background thread gay treo tien trinh tren Windows).
    """
    global _cached_config, _last_mtime
    try:
        current_mtime = CONFIG_PATH.stat().st_mtime
        if not _cached_config or current_mtime != _last_mtime:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                _cached_config = json.load(f)
            _last_mtime = current_mtime
    except Exception:
        if not _cached_config:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                _cached_config = json.load(f)
    return dict(_cached_config)


config = load_config()


def save_config(new_data: dict) -> dict:
    """Cap nhat va luu file chatbot_config.json (merge an toan voi config hien tai)."""
    global config, _cached_config, _last_mtime
    merged = {**load_config(), **new_data}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    _cached_config = merged
    _last_mtime = CONFIG_PATH.stat().st_mtime
    config = merged
    return merged
