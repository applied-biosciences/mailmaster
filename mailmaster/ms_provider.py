"""Outlook.com / Hotmail / Microsoft 365 accounts via Microsoft Graph."""
import auth
import graph


class NeedsSignIn(Exception):
    pass


def _token(acc):
    tok = auth.get_token(acc["home_account_id"])
    if not tok:
        raise NeedsSignIn("Sign-in expired. Remove and re-add this account.")
    return tok


def _normalize(m, folder):
    sender = (m.get("from") or {}).get("emailAddress") or {}
    return {
        "id": m["id"], "folder": folder,
        "subject": m.get("subject") or "",
        "fromName": sender.get("name") or sender.get("address") or "",
        "fromAddress": (sender.get("address") or "").lower(),
        "received": m.get("receivedDateTime"),
        "preview": (m.get("bodyPreview") or "")[:300],
        "isRead": m.get("isRead", True),
        "flagged": (m.get("flag") or {}).get("flagStatus") == "flagged",
        "importance": m.get("importance") or "normal",
        "focused": m.get("inferenceClassification"),
        "headers": {h["name"].lower(): h["value"] for h in (m.get("internetMessageHeaders") or [])},
        "webLink": m.get("webLink"),
    }


def fetch(acc, limit, junk_limit, deleted_limit):
    tok = _token(acc)
    out = [_normalize(m, "inbox") for m in graph.list_messages(tok, "inbox", limit)]
    out += [_normalize(m, "junk") for m in graph.list_messages(tok, "junkemail", junk_limit)]
    out += [_normalize(m, "deleted") for m in graph.list_messages(tok, "deleteditems", deleted_limit)]
    return out


def fetch_deleted(acc, n):
    return [_normalize(m, "deleted") for m in graph.list_messages(_token(acc), "deleteditems", n)]


def delete(acc, items, permanent):
    """items: normalized messages. Emails already in Deleted Items are always deleted permanently.
    Returns list of deleted native ids."""
    tok = _token(acc)
    hard = [m["id"] for m in items if permanent or m["folder"] == "deleted"]
    soft = [m["id"] for m in items if not (permanent or m["folder"] == "deleted")]
    done = []
    if hard:
        done += graph.delete_messages(tok, hard, True)[0]
    if soft:
        done += graph.delete_messages(tok, soft, False)[0]
    return done


def send(acc, to, subject, body):
    graph.send_mail(_token(acc), to, subject, body)
