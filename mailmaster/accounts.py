"""Stores the list of connected accounts in accounts.json.
IMAP passwords go into the macOS Keychain (via `keyring`) when available."""
import hashlib
import json
import os
import threading

import config

FILE = config.ACCOUNTS_FILE
KEYRING_SERVICE = "MailMaster"
_lock = threading.Lock()


def make_id(prefix, *parts):
    return f"{prefix}-" + hashlib.sha1("|".join(parts).lower().encode()).hexdigest()[:10]


def load():
    if not os.path.exists(FILE):
        return []
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(items):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    try:
        os.chmod(FILE, 0o600)
    except OSError:
        pass


def get(acc_id):
    return next((a for a in load() if a["id"] == acc_id), None)


def upsert(acc):
    with _lock:
        items = [a for a in load() if a["id"] != acc["id"]] + [acc]
        _save(items)


def remove(acc_id):
    with _lock:
        _save([a for a in load() if a["id"] != acc_id])
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, acc_id)
    except Exception:  # noqa: BLE001
        pass


def set_password(acc, password):
    """Stores the password in Keychain if possible, otherwise in accounts.json."""
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, acc["id"], password)
        acc.pop("password", None)
        acc["password_in"] = "keychain"
    except Exception:  # noqa: BLE001
        acc["password"] = password
        acc["password_in"] = "file"


def get_password(acc):
    if acc.get("password_in") == "keychain":
        import keyring
        return keyring.get_password(KEYRING_SERVICE, acc["id"])
    return acc.get("password")


def public(acc):
    return {k: v for k, v in acc.items() if k not in ("password", "home_account_id")}
