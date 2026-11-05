"""Gmail, iCloud, Yahoo and any other IMAP account (uses an app password)."""
import email
import email.policy
import email.utils
import imaplib
import quopri
import re
import smtplib
from email.message import EmailMessage
from datetime import timezone

import accounts

PRESETS = {
    "gmail":  {"label": "Gmail",  "imap_host": "imap.gmail.com",      "imap_port": 993, "smtp_host": "smtp.gmail.com",      "smtp_port": 465},
    "icloud": {"label": "iCloud", "imap_host": "imap.mail.me.com",    "imap_port": 993, "smtp_host": "smtp.mail.me.com",    "smtp_port": 587},
    "yahoo":  {"label": "Yahoo",  "imap_host": "imap.mail.yahoo.com", "imap_port": 993, "smtp_host": "smtp.mail.yahoo.com", "smtp_port": 465},
    "other":  {"label": "IMAP",   "imap_host": "",                    "imap_port": 993, "smtp_host": "",                    "smtp_port": 465},
}

HEADER_FIELDS = ("FROM SUBJECT DATE MESSAGE-ID LIST-UNSUBSCRIBE LIST-UNSUBSCRIBE-POST "
                 "LIST-ID PRECEDENCE IMPORTANCE X-PRIORITY")
JUNK_NAMES = ["[Gmail]/Spam", "Junk", "Junk Email", "Junk E-mail", "Spam", "Bulk Mail", "Bulk"]
TRASH_NAMES = ["[Gmail]/Trash", "[Gmail]/Bin", "Trash", "Deleted Items", "Deleted Messages", "Bin"]


# ---------- connection ----------
def connect(acc, password=None):
    M = imaplib.IMAP4_SSL(acc["imap_host"], int(acc.get("imap_port") or 993), timeout=30)
    M.login(acc.get("username") or acc["email"], password or accounts.get_password(acc) or "")
    return M


def test_login(acc, password):
    M = connect(acc, password)
    try:
        M.logout()
    except Exception:  # noqa: BLE001
        pass


def _q(name):
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


LIST_RE = re.compile(rb'\((?P<flags>[^)]*)\)\s+(?P<delim>"[^"]*"|NIL)\s+(?P<name>.+)$')


def special_folders(M):
    """Finds the Junk/Spam and Trash folders using IMAP special-use flags, then common names."""
    found, names = {}, []
    typ, data = M.list()
    for line in data or []:
        if isinstance(line, tuple):
            line = line[0] + line[1]
        m = LIST_RE.match(line or b"")
        if not m:
            continue
        name = m.group("name").decode("utf-8", "replace").strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        names.append(name)
        flags = m.group("flags").lower()
        if b"\\junk" in flags:
            found.setdefault("junk", name)
        if b"\\trash" in flags:
            found.setdefault("trash", name)
    lower = {n.lower(): n for n in names}
    for key, options in (("junk", JUNK_NAMES), ("trash", TRASH_NAMES)):
        if key not in found:
            found[key] = next((lower[o.lower()] for o in options if o.lower() in lower), None)
    return found


# ---------- parsing ----------
def _parse_fetch(data):
    """Splits an IMAP UID FETCH response into per-message dicts {uid, flags, header, text}."""
    msgs, cur = [], None
    for item in data or []:
        meta, literal = (item[0], item[1]) if isinstance(item, tuple) else (item, None)
        if meta is None:
            continue
        if re.match(rb"^\d+ \(", meta):
            cur = {"meta": b"", "header": b"", "text": b""}
            msgs.append(cur)
        if cur is None:
            continue
        cur["meta"] += meta + b" "
        if literal is not None:
            if meta.rfind(b"HEADER.FIELDS") > meta.rfind(b"BODY[TEXT]"):
                cur["header"] = literal
            else:
                cur["text"] = literal
    out = []
    for c in msgs:
        uid = re.search(rb"UID (\d+)", c["meta"])
        flags = re.search(rb"FLAGS \(([^)]*)\)", c["meta"])
        if uid:
            out.append({"uid": uid.group(1).decode(), "flags": (flags.group(1).decode() if flags else ""),
                        "header": c["header"], "text": c["text"]})
    return out


def _preview(raw):
    """Best-effort readable snippet from the first bytes of a message body."""
    if not raw:
        return ""
    txt = raw.decode("utf-8", "replace")
    if "quoted-printable" in txt.lower() or "=\r\n" in txt:
        try:
            txt = quopri.decodestring(raw).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
    lines = []
    for ln in txt.splitlines():
        s = ln.strip()
        if not s or s.startswith("--") or re.match(r"^[\w-]+:\s", s):
            continue  # MIME boundaries / part headers
        if re.fullmatch(r"[A-Za-z0-9+/=]{60,}", s):
            continue  # base64 blob
        lines.append(s)
    txt = " ".join(lines)
    txt = re.sub(r"<style.*?</style>|<script.*?</script>", " ", txt, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;|&#160;", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()[:300]


def _normalize(acc, folder_key, p):
    msg = email.message_from_bytes(p["header"], policy=email.policy.default)
    try:
        addr = msg["from"].addresses[0]
        name, address = addr.display_name, addr.addr_spec
    except Exception:  # noqa: BLE001
        name, address = email.utils.parseaddr(str(msg.get("from", "")))
    try:
        dt = email.utils.parsedate_to_datetime(str(msg["date"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        received = dt.astimezone(timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        received = None
    headers = {k.lower(): str(v) for k, v in msg.items()}
    prio = headers.get("x-priority", "").strip()[:1]
    importance = "high" if headers.get("importance", "").lower() == "high" or prio in ("1", "2") else "normal"
    web = None
    if acc.get("provider") == "gmail" and headers.get("message-id"):
        mid = headers["message-id"].strip("<> ")
        web = f"https://mail.google.com/mail/u/?authuser={acc['email']}#search/rfc822msgid%3A{mid}"
    return {
        "id": f"{folder_key}:{p['uid']}", "folder": folder_key,
        "subject": str(msg.get("subject", "") or ""),
        "fromName": name or address or "", "fromAddress": (address or "").lower(),
        "received": received, "preview": _preview(p["text"]),
        "isRead": "\\Seen" in p["flags"], "flagged": "\\Flagged" in p["flags"],
        "importance": importance, "focused": None, "headers": headers, "webLink": web,
    }


# ---------- operations ----------
def _folder_names(special):
    return {"inbox": "INBOX", "junk": special.get("junk"), "deleted": special.get("trash")}


def fetch(acc, limit, junk_limit, deleted_limit):
    return _fetch(acc, [("inbox", limit), ("junk", junk_limit), ("deleted", deleted_limit)])


def fetch_deleted(acc, n):
    return _fetch(acc, [("deleted", n)])


def _fetch(acc, wanted):
    M = connect(acc)
    out = []
    try:
        names = _folder_names(special_folders(M))
        for key, n in wanted:
            folder = names.get(key)
            if not folder or n <= 0:
                continue
            typ, _ = M.select(_q(folder), readonly=True)
            if typ != "OK":
                continue
            typ, data = M.uid("SEARCH", None, "ALL")
            uids = (data[0] or b"").split()[-n:] if typ == "OK" else []
            for i in range(0, len(uids), 100):
                chunk = b",".join(uids[i:i + 100]).decode()
                typ, data = M.uid("FETCH", chunk,
                                  f"(UID FLAGS BODY.PEEK[HEADER.FIELDS ({HEADER_FIELDS})] BODY.PEEK[TEXT]<0.2000>)")
                if typ == "OK":
                    out += [_normalize(acc, key, p) for p in _parse_fetch(data)]
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass
    return out


def delete(acc, items, permanent):
    """Moves to Trash (or permanently deletes). Emails already in Trash are deleted for good.
    Gmail: inbox/spam deletes always go to Trash (Gmail empties it after 30 days)."""
    M = connect(acc)
    deleted = []
    try:
        special = special_folders(M)
        trash = special.get("trash")
        caps = {c.decode().upper() if isinstance(c, bytes) else str(c).upper() for c in M.capabilities}
        by_folder = {}
        for m in items:
            key, uid = m["id"].split(":", 1)
            by_folder.setdefault(key, []).append((m["id"], uid))
        names = _folder_names(special)
        for key, pairs in by_folder.items():
            folder = names.get(key)
            if not folder or M.select(_q(folder))[0] != "OK":
                continue
            uidset = ",".join(u for _, u in pairs)
            in_trash = key == "deleted"
            to_trash = not in_trash and trash and (not permanent or acc.get("provider") == "gmail")
            if in_trash:  # already in Trash: delete for good
                ok = M.uid("STORE", uidset, "+FLAGS.SILENT", r"(\Deleted)")[0] == "OK"
                if ok:
                    M.uid("EXPUNGE", uidset) if "UIDPLUS" in caps else M.expunge()
            elif to_trash:
                if "MOVE" in caps:
                    ok = M.uid("MOVE", uidset, _q(trash))[0] == "OK"
                else:
                    ok = M.uid("COPY", uidset, _q(trash))[0] == "OK"
                    if ok:
                        M.uid("STORE", uidset, "+FLAGS.SILENT", r"(\Deleted)")
                        M.uid("EXPUNGE", uidset) if "UIDPLUS" in caps else M.expunge()
            elif permanent:
                ok = M.uid("STORE", uidset, "+FLAGS.SILENT", r"(\Deleted)")[0] == "OK"
                if ok:
                    M.uid("EXPUNGE", uidset) if "UIDPLUS" in caps else M.expunge()
            else:
                raise RuntimeError("No Trash folder found for this account. Tick 'Delete permanently' to delete.")
            if ok:
                deleted += [i for i, _ in pairs]
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass
    return deleted


def send(acc, to, subject, body):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = acc["email"], to, subject or "unsubscribe"
    msg.set_content(body or "unsubscribe")
    host, port = acc["smtp_host"], int(acc.get("smtp_port") or 465)
    user, pw = acc.get("username") or acc["email"], accounts.get_password(acc)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, pw)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
