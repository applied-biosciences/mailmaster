"""Sample accounts and emails used when DEMO_MODE=1 (try the app without connecting anything)."""
from datetime import datetime, timedelta, timezone

ACCOUNTS = [
    {"id": "demo-outlook", "type": "microsoft", "provider": "outlook", "email": "you@outlook.com", "name": "Outlook"},
    {"id": "demo-gmail", "type": "imap", "provider": "gmail", "email": "you@gmail.com", "name": "Gmail"},
    {"id": "demo-imap", "type": "imap", "provider": "other", "email": "you@yourcompany.com", "name": "Work IMAP"},
]

LIST = {"list-unsubscribe": "<mailto:unsub@news.example.com?subject=unsubscribe>, <https://news.example.com/u/123>"}
ONECLICK = {"list-unsubscribe": "<https://shop.example.com/unsub?id=9>",
            "list-unsubscribe-post": "List-Unsubscribe=One-Click"}
LINK = {"list-unsubscribe": "<https://medium.com/unsub/abc>"}

_RAW = {
    "demo-outlook": [
        ("Sarah Ahmed", "sarah@partnerco.com", "Contract draft for Monday", "Attached is the revised draft. Can you review before our call?", {}, "high", "inbox"),
        ("PayPal", "service@paypal.co.uk", "Receipt for your payment to Uber", "You sent a payment of £14.20.", {}, "normal", "inbox"),
        ("Microsoft account", "account-security-noreply@accountprotection.microsoft.com", "Microsoft account security alert", "We detected a new sign-in to your account.", {}, "normal", "inbox"),
        ("The Batch", "hello@news.example.com", "This week in AI", "Top stories on models, agents and research.", LIST, "normal", "inbox"),
        ("Prize Center", "winner@prize-claims.biz", "You have WON an iPhone", "Click here to claim your prize now.", {}, "normal", "junk"),
        ("Old Newsletter", "news@oldsite.example", "Our final issue", "Thanks for reading over the years.", {}, "normal", "deleted"),
    ],
    "demo-gmail": [
        ("Omar Khan", "omar.khan@gmail.com", "Dinner on Saturday?", "Are you free this weekend? Thinking of the new place in town.", {}, "normal", "inbox"),
        ("Amazon", "auto-confirm@amazon.co.uk", "Your order #204-55 has shipped", "Your package is on its way.", {}, "normal", "inbox"),
        ("StyleShop", "deals@shop.example.com", "48 hours only: 40% off everything", "Shop now, sale ends Sunday.", ONECLICK, "normal", "inbox"),
        ("StyleShop", "deals@shop.example.com", "Black Friday early access", "Exclusive deals for members.", ONECLICK, "normal", "inbox"),
        ("Medium Daily Digest", "noreply@medium.com", "Stories for you", "Based on your reading history.", LINK, "normal", "inbox"),
        ("Crypto Pro", "invest@quick-returns.co", "Double your money in 7 days", "Guaranteed returns.", {}, "normal", "junk"),
        ("Uber Eats", "uber@uber.com", "Your Tuesday order with Uber Eats", "Thanks for ordering.", {}, "normal", "deleted"),
    ],
    "demo-imap": [
        ("Finance Team", "finance@yourcompany.com", "Q4 budget sign-off needed", "Please approve by Friday.", {}, "normal", "inbox"),
        ("GitHub", "noreply@github.com", "[GitHub] A new SSH key was added", "A new public key was added to your account.", {}, "normal", "inbox"),
        ("The Batch", "hello@news.example.com", "Issue 212: agents in production", "What we learned from deploying agents.", LIST, "normal", "inbox"),
    ],
}


_STATE = {}   # acc_id -> list of messages (so deletes in demo mode behave like a real mailbox)
_COUNTER = [1000]


def _seed(acc_id):
    out = []
    for i, (name, addr, subj, prev, headers, imp, folder) in enumerate(_RAW.get(acc_id, [])):
        out.append({
            "id": f"{folder}:{i}", "folder": folder, "subject": subj, "fromName": name, "fromAddress": addr,
            "received": (datetime.now(timezone.utc) - timedelta(hours=i * 7 + len(acc_id))).isoformat(),
            "preview": prev, "isRead": i % 3 == 0, "flagged": False, "importance": imp,
            "focused": None, "headers": dict(headers), "webLink": None,
        })
    return out


def messages(acc_id, folder=None):
    msgs = _STATE.setdefault(acc_id, _seed(acc_id))
    return [dict(m) for m in msgs if folder is None or m["folder"] == folder]


def delete(acc_id, items, permanent):
    """Moves to the demo Trash (new id, like a real server), or removes for good."""
    msgs = _STATE.setdefault(acc_id, _seed(acc_id))
    ids = {m["id"] for m in items}
    done = []
    for m in list(msgs):
        if m["id"] not in ids:
            continue
        done.append(m["id"])
        if permanent or m["folder"] == "deleted":
            msgs.remove(m)
        else:
            _COUNTER[0] += 1
            m["folder"], m["id"] = "deleted", f"deleted:{_COUNTER[0]}"
    return done
