"""MailMaster - one place to sort, clean up and unsubscribe across Outlook, Gmail and IMAP accounts.
Desktop app entry point: desktop.py.  Developers: `python mailmaster/app.py`, then open http://localhost:3500
"""
import os
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, redirect, render_template, request, url_for
from markupsafe import escape

import accounts
import classifier
import config
import imap_provider
import saved_passwords
import settings
import unsubscribe

if config.DEMO_MODE:
    import demo_data
else:
    import auth
    import ms_provider

app = Flask(__name__, template_folder=os.path.join(config.RESOURCE_DIR, "templates"),
            static_folder=os.path.join(config.RESOURCE_DIR, "static"))
app.secret_key = config.FLASK_SECRET

# Last fetch, keyed "accountId|nativeId" -> {"acc": account, "m": normalized msg, "category", "reason"}
STORE = {}

# Microsoft sign-ins in progress, keyed by OAuth state (sign-in happens in the person's normal browser)
FLOWS = {}
_flows_lock = threading.Lock()


# ---------- protection for a server that runs on the person's own computer ----------
@app.before_request
def guard_local_requests():
    """Only answer requests addressed to this computer, and only accept changes from MailMaster's own page.
    Stops websites open in the person's browser from triggering actions (CSRF / DNS rebinding)."""
    if request.host.split(":")[0] not in ("localhost", "127.0.0.1"):
        return "Forbidden", 403
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.headers.get("X-MailMaster") != "1":
        return jsonify({"error": "Request not allowed."}), 403
    return None


# ---------- accounts & providers ----------
def all_accounts():
    return list(demo_data.ACCOUNTS) if config.DEMO_MODE else accounts.load()


def provider(acc):
    return ms_provider if acc["type"] == "microsoft" else imap_provider


def fetch_account(acc):
    if config.DEMO_MODE:
        return demo_data.messages(acc["id"])
    s = settings.load()
    return provider(acc).fetch(acc, settings.limit(s["max_inbox"]), settings.limit(s["max_junk"]),
                               settings.limit(s["max_deleted"]))


def fetch_deleted_for_account(acc):
    if config.DEMO_MODE:
        return demo_data.messages(acc["id"], "deleted")
    return provider(acc).fetch_deleted(acc, settings.limit(settings.load()["max_deleted"]))


def delete_for_account(acc, items, permanent):
    if config.DEMO_MODE:
        return demo_data.delete(acc["id"], items, permanent)
    return provider(acc).delete(acc, items, permanent)


def send_for_account(acc, to, subject, body):
    if not config.DEMO_MODE:
        provider(acc).send(acc, to, subject, body)


def add_to_store(acc, m):
    cat, reason = classifier.classify(m)
    key = f"{acc['id']}|{m['id']}"
    STORE[key] = {"acc": acc, "m": m, "category": cat, "reason": reason}
    return key


def refresh_store():
    STORE.clear()
    accs = all_accounts()
    errors = {}
    with ThreadPoolExecutor(max_workers=max(1, min(6, len(accs)))) as pool:
        futures = {pool.submit(fetch_account, a): a for a in accs}
        for fut, acc in futures.items():
            try:
                for m in fut.result():
                    add_to_store(acc, m)
            except Exception as e:  # noqa: BLE001
                errors[acc["id"]] = str(e)[:300]
    return errors


def serialize(key):
    e = STORE[key]
    m, acc = e["m"], e["acc"]
    return {
        "id": key, "accountId": acc["id"], "subject": m["subject"] or "(no subject)",
        "fromName": m["fromName"], "fromAddress": m["fromAddress"], "received": m["received"],
        "preview": m["preview"][:200], "isRead": m["isRead"], "webLink": m.get("webLink"),
        "category": e["category"], "reason": e["reason"],
        "unsubscribe": unsubscribe.method(unsubscribe.options(m["headers"])),
    }


def delete_keys(keys, permanent):
    """Deletes across accounts. Emails already in Deleted Mail are deleted for good.
    Returns {"deleted": keys, "errors": [...], "trash": {accountId: [fresh Deleted Mail items]}}."""
    by_acc = {}
    for k in dict.fromkeys(keys):
        if k in STORE:
            by_acc.setdefault(STORE[k]["acc"]["id"], []).append(k)
    deleted, errors, moved = [], [], {}
    for acc_id, ks in by_acc.items():
        acc = STORE[ks[0]]["acc"]
        try:
            done = set(delete_for_account(acc, [STORE[k]["m"] for k in ks], permanent))
            for k in ks:
                if STORE[k]["m"]["id"] in done:
                    if not permanent and STORE[k]["m"]["folder"] != "deleted":
                        moved[acc_id] = acc
                    deleted.append(k)
                    STORE.pop(k, None)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{acc['email']}: {e}")
    return {"deleted": deleted, "errors": errors, "trash": refresh_trash(moved.values(), errors)}


def refresh_trash(accs, errors):
    """Re-reads Deleted Items / Trash for these accounts (moved emails get new ids there)."""
    out = {}
    for acc in accs:
        try:
            fresh = fetch_deleted_for_account(acc)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{acc['email']} (reading Trash): {e}")
            continue
        for k in [k for k, v in STORE.items() if v["acc"]["id"] == acc["id"] and v["m"]["folder"] == "deleted"]:
            STORE.pop(k)
        out[acc["id"]] = [serialize(add_to_store(acc, m)) for m in fresh]
    return out


# ---------- desktop helpers ----------
@app.route("/api/ping")
def api_ping():
    return jsonify({"app": config.APP_NAME, "version": config.VERSION})


@app.route("/api/open-url", methods=["POST"])
def api_open_url():
    """Opens a web link in the person's normal browser (the app window can't show other sites)."""
    url = ((request.get_json(force=True) or {}).get("url") or "").strip()
    if not url.lower().startswith(("https://", "http://")):
        return jsonify({"error": "Only web links can be opened."}), 400
    webbrowser.open(url)
    return jsonify({"ok": True})


# ---------- pages ----------
@app.route("/")
def index():
    return render_template("index.html", demo=config.DEMO_MODE, version=config.VERSION, app_name=config.APP_NAME)


# ---------- Microsoft sign-in ----------
# Sign-in opens in the person's normal web browser, so any Microsoft login already saved there
# (Outlook on the web, Microsoft 365, Edge signed in with Windows) is reused: they just pick the account.
NO_MS_ID = ("This copy of MailMaster has no Microsoft app ID, so Outlook accounts can't be added. "
            "Use an official build, or set CLIENT_ID (see README).")


def _new_flow():
    flow = auth.start_login()
    with _flows_lock:
        now = time.time()
        for k in [k for k, (_, t) in FLOWS.items() if now - t > 900]:  # forget sign-ins older than 15 min
            FLOWS.pop(k, None)
        FLOWS[flow["state"]] = (flow, now)
    return flow


@app.route("/api/ms-login/start", methods=["POST"])
def api_ms_login_start():
    if config.DEMO_MODE:
        return jsonify({"error": "Adding accounts is turned off in demo mode."}), 400
    if not config.CLIENT_ID:
        return jsonify({"error": NO_MS_ID}), 400
    flow = _new_flow()
    webbrowser.open(flow["auth_uri"])
    return jsonify({"ok": True, "url": flow["auth_uri"]})


@app.route("/login/microsoft")
def login_ms():
    """Same-tab sign-in (used when MailMaster itself runs in a browser tab)."""
    if config.DEMO_MODE:
        return redirect(url_for("index"))
    if not config.CLIENT_ID:
        return NO_MS_ID, 400
    return redirect(_new_flow()["auth_uri"])


def _result_page(title, body, ok=True):
    color = "#1a8a5a" if ok else "#c8372d"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>MailMaster</title>
<link rel="icon" href="/static/favicon-32.png"></head>
<body style="font:16px system-ui,-apple-system,'Segoe UI',sans-serif;background:#f6f7f9;color:#1d2330;
display:grid;place-items:center;min-height:90vh;margin:0">
<div style="background:#fff;border:1px solid #e4e7ec;border-radius:16px;padding:32px 40px;max-width:520px;text-align:center">
<img src="/static/logo.png" width="72" alt=""><h2 style="color:{color};margin:12px 0">{title}</h2>
<p style="color:#4a5163;line-height:1.5">{body}</p></div></body></html>"""


@app.route("/auth/callback")
def callback():
    state = request.args.get("state", "")
    with _flows_lock:
        entry = FLOWS.pop(state, None)
    if not entry:
        return _result_page("Sign-in expired", "Please go back to MailMaster and click <b>Outlook</b> again.", ok=False), 400
    info, err = auth.finish_login(entry[0], request.args)
    if err:
        return _result_page("Sign-in failed", f"<code style='white-space:pre-wrap'>{escape(err)}</code>", ok=False), 400
    accounts.upsert({"id": accounts.make_id("ms", info["home_account_id"]), "type": "microsoft",
                     "provider": "outlook", "email": info["username"], "name": "Outlook",
                     "home_account_id": info["home_account_id"]})
    STORE.clear()
    return _result_page(f"Signed in as {escape(info['username'])}",
                        "You can close this tab and go back to MailMaster. Your mail will appear in a moment.")


# ---------- API: accounts ----------
@app.route("/api/accounts")
def api_accounts():
    presets = {k: {"label": v["label"], "imap_host": v["imap_host"], "smtp_host": v["smtp_host"],
                   "imap_port": v["imap_port"], "smtp_port": v["smtp_port"]}
               for k, v in imap_provider.PRESETS.items()}
    return jsonify({"accounts": [accounts.public(a) for a in all_accounts()], "presets": presets,
                    "msConfigured": bool(config.CLIENT_ID), "demo": config.DEMO_MODE})


@app.route("/api/accounts/imap", methods=["POST"])
def api_add_imap():
    if config.DEMO_MODE:
        return jsonify({"error": "Adding accounts is turned off in demo mode. Set DEMO_MODE=0 in .env."}), 400
    b = request.get_json(force=True) or {}
    prov = b.get("provider", "other")
    preset = imap_provider.PRESETS.get(prov, imap_provider.PRESETS["other"])
    email_addr = (b.get("email") or "").strip()
    password = (b.get("password") or "").replace(" ", "") if prov == "gmail" else (b.get("password") or "")
    acc = {
        "type": "imap", "provider": prov, "email": email_addr,
        "username": (b.get("username") or email_addr).strip(),
        "name": (b.get("name") or "").strip() or (preset["label"] if prov != "other" else "IMAP"),
        "imap_host": (b.get("imap_host") or preset["imap_host"]).strip(),
        "imap_port": int(b.get("imap_port") or preset["imap_port"]),
        "smtp_host": (b.get("smtp_host") or preset["smtp_host"]).strip(),
        "smtp_port": int(b.get("smtp_port") or preset["smtp_port"]),
    }
    if not (email_addr and password and acc["imap_host"]):
        return jsonify({"error": "Email, password and IMAP server are required."}), 400
    try:
        imap_provider.test_login(acc, password)
    except Exception as e:  # noqa: BLE001
        hint = " For Gmail/iCloud/Yahoo use an app password, not your normal password." if prov != "other" else ""
        return jsonify({"error": f"Could not sign in: {e}.{hint}"}), 400
    acc["id"] = accounts.make_id("imap", email_addr, acc["imap_host"])
    accounts.set_password(acc, password)
    accounts.upsert(acc)
    STORE.clear()
    return jsonify({"ok": True, "account": accounts.public(acc)})


@app.route("/api/saved-password", methods=["POST"])
def api_saved_password():
    """Finds a password saved on this computer (Keychain / Credential Manager) for the account being added."""
    if config.DEMO_MODE:
        return jsonify({"error": "Turned off in demo mode."}), 400
    b = request.get_json(force=True) or {}
    preset = imap_provider.PRESETS.get(b.get("provider", "other"), imap_provider.PRESETS["other"])
    hosts = [b.get("imap_host") or preset["imap_host"], b.get("smtp_host") or preset["smtp_host"]]
    pw, where = saved_passwords.find(b.get("email", ""), b.get("username", ""), hosts)
    if not pw:
        return jsonify({"found": False, "message": where})
    return jsonify({"found": True, "password": pw, "message": f"Filled in from {where}."})


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        try:
            data = settings.save(request.get_json(force=True) or {})
        except (ValueError, TypeError) as e:
            return jsonify({"error": str(e)}), 400
        STORE.clear()
        return jsonify({"settings": data})
    return jsonify({"settings": settings.load(), "choices": settings.LIMIT_CHOICES})


@app.route("/api/accounts/<acc_id>", methods=["DELETE"])
def api_remove_account(acc_id):
    if config.DEMO_MODE:
        return jsonify({"error": "Turned off in demo mode."}), 400
    acc = accounts.get(acc_id)
    if acc and acc["type"] == "microsoft":
        auth.remove(acc["home_account_id"])
    accounts.remove(acc_id)
    STORE.clear()
    return jsonify({"ok": True})


# ---------- API: mail ----------
@app.route("/api/summary")
def api_summary():
    errors = {}
    if request.args.get("refresh") == "1" or not STORE:
        errors = refresh_store()
    items = sorted((serialize(k) for k in STORE), key=lambda x: x["received"] or "", reverse=True)
    return jsonify({"categories": classifier.CATEGORIES, "items": items, "errors": errors,
                    "accounts": [accounts.public(a) for a in all_accounts()]})


@app.route("/api/delete", methods=["POST"])
def api_delete():
    b = request.get_json(force=True) or {}
    return jsonify(delete_keys(b.get("ids", []), bool(b.get("permanent"))))


def unsubscribe_one(key):
    """Unsubscribes using one email's headers. Returns result dict."""
    e = STORE[key]
    acc, m = e["acc"], e["m"]
    opts = unsubscribe.options(m["headers"])
    base = {"sender": m["fromAddress"], "name": m["fromName"]}
    if not opts:
        return {**base, "status": "failed", "message": "No unsubscribe option."}
    if config.DEMO_MODE:
        meth = unsubscribe.method(opts)
        res = ({"status": "open_link", "url": opts["http_url"], "message": "Demo: would open the sender's page."}
               if meth == "link" else {"status": "done", "message": f"Demo: unsubscribed via {meth}."})
    else:
        try:
            res = unsubscribe.perform(opts, lambda to, s, body: send_for_account(acc, to, s, body))
        except Exception as ex:  # noqa: BLE001
            res = {"status": "failed", "message": str(ex)[:200]}
    return {**base, **res}


def delete_from_senders(senders, permanent):
    senders = set(senders)
    keys = [k for k, v in STORE.items() if v["m"]["fromAddress"] in senders and v["m"]["folder"] != "deleted"]
    return delete_keys(keys, permanent)


@app.route("/api/unsubscribe", methods=["POST"])
def api_unsubscribe():
    b = request.get_json(force=True) or {}
    key = b.get("id")
    if key not in STORE:
        return jsonify({"error": "Email not found, refresh and try again."}), 404
    result = unsubscribe_one(key)
    result.update({"deleted": [], "errors": [], "trash": {}})
    if b.get("deleteAll") and result["status"] in ("done", "open_link"):
        result.update(delete_from_senders([result["sender"]], bool(b.get("permanent"))))
    return jsonify(result)


@app.route("/api/unsubscribe/bulk", methods=["POST"])
def api_unsubscribe_bulk():
    """Unsubscribes from every sender in the selection (once per sender)."""
    b = request.get_json(force=True) or {}
    per_sender = {}
    for k in b.get("ids", []):
        if k in STORE and unsubscribe.options(STORE[k]["m"]["headers"]):
            per_sender.setdefault(STORE[k]["m"]["fromAddress"], k)
    if not per_sender:
        return jsonify({"error": "None of the selected emails can be unsubscribed."}), 400
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(unsubscribe_one, per_sender.values()))
    out = {"results": results, "deleted": [], "errors": [], "trash": {}}
    ok_senders = [r["sender"] for r in results if r["status"] in ("done", "open_link")]
    if b.get("deleteAll") and ok_senders:
        out.update(delete_from_senders(ok_senders, bool(b.get("permanent"))))
    return jsonify(out)


if __name__ == "__main__":
    print(f"\n  {config.APP_NAME} v{config.VERSION} running at http://localhost:{config.PORT}"
          f"{'  (DEMO MODE: sample emails)' if config.DEMO_MODE else ''}\n  Press Ctrl+C to stop.\n")
    # Localhost only, so nobody else on your network can reach your mailboxes.
    app.run(host="127.0.0.1", port=config.PORT, debug=False)
