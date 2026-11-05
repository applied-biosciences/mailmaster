"""Settings. Order of precedence: environment variables > .env in the data folder > .env in the
current folder (developers) > values built into the app."""
import os
import secrets
import sys

from dotenv import load_dotenv

from version import APP_NAME, VERSION  # noqa: F401  (re-exported)

FROZEN = getattr(sys, "frozen", False)  # True inside the packaged desktop app

# Read-only files shipped with the app (templates, static)
RESOURCE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _data_dir():
    """Where each person's accounts and sign-ins are stored."""
    if os.getenv("MAILMASTER_DATA"):
        return os.path.expanduser(os.getenv("MAILMASTER_DATA"))
    if not FROZEN:  # running from source: keep data next to the code, as in v1.x
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/MailMaster")
    if os.name == "nt":
        return os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "MailMaster")
    return os.path.join(os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "mailmaster")


DATA_DIR = _data_dir()
os.makedirs(DATA_DIR, exist_ok=True)

load_dotenv(os.path.join(DATA_DIR, ".env"))
load_dotenv()  # .env in the current folder (does not override values already set)

try:
    from build_info import CLIENT_ID as _BUILT_IN_CLIENT_ID
except ImportError:  # pragma: no cover
    _BUILT_IN_CLIENT_ID = ""

CLIENT_ID = (os.getenv("CLIENT_ID") or _BUILT_IN_CLIENT_ID or "").strip()
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "").strip()  # optional; leave empty (desktop / public client)
AUTHORITY = os.getenv("AUTHORITY", "https://login.microsoftonline.com/common").strip()
PORT = int(os.getenv("PORT", "3500"))
REDIRECT_URI = os.getenv("REDIRECT_URI", f"http://localhost:{PORT}/auth/callback").strip()
FLASK_SECRET = os.getenv("FLASK_SECRET") or secrets.token_hex(32)
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "300"))  # per account, inbox
MAX_JUNK = int(os.getenv("MAX_JUNK", "100"))  # per account, junk/spam folder
MAX_DELETED = int(os.getenv("MAX_DELETED", "100"))  # per account, Deleted Items / Trash
DEMO_MODE = os.getenv("DEMO_MODE", "0").strip().lower() in ("1", "true", "yes")

# Delegated Microsoft Graph permissions (offline_access is added automatically by MSAL)
SCOPES = ["User.Read", "Mail.ReadWrite", "Mail.Send"]

TOKEN_CACHE_FILE = os.path.join(DATA_DIR, "token_cache.json")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
LOG_FILE = os.path.join(DATA_DIR, "mailmaster.log")
