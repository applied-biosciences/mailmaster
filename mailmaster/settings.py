"""Per-person settings chosen in the app (stored in settings.json in the data folder)."""
import json
import os
import threading

import config

FILE = os.path.join(config.DATA_DIR, "settings.json")
_lock = threading.Lock()

# How many emails to load per account from each folder. 0 means "Max" (everything in the folder).
LIMIT_CHOICES = [100, 300, 500, 1000, 2000, 5000, 0]
DEFAULTS = {
    "max_inbox": config.MAX_MESSAGES,
    "max_junk": config.MAX_JUNK,
    "max_deleted": config.MAX_DELETED,
}


def load():
    data = dict(DEFAULTS)
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        data.update({k: int(v) for k, v in saved.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return data


def save(new):
    with _lock:
        data = load()
        for k in DEFAULTS:
            if k in new:
                v = int(new[k])
                if v < 0:
                    raise ValueError(f"{k} must be 0 (Max) or a positive number")
                data[k] = v
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data


def limit(value):
    """Settings store 0 for 'Max'; providers take None for 'no limit'."""
    return None if not value else int(value)
