"""Sorts each email into one of six groups using simple, readable rules.
Edit the keyword lists below to tune it to your inbox."""
import re

CATEGORIES = ["Priority", "Transactions", "Updates", "Promotions", "Mailing List", "Junk", "Deleted Mail"]

TRANSACTION_WORDS = [
    "receipt", "invoice", "your order", "order confirmation", "order #", "order no",
    "payment", "paid", "refund", "has shipped", "shipped", "dispatched", "delivery",
    "delivered", "out for delivery", "tracking", "booking confirmation", "reservation",
    "e-ticket", "itinerary", "statement", "transaction", "purchase", "subscription renewal",
    "direct debit", "bank transfer", "billing",
]
PROMO_WORDS = [
    "% off", "sale", "discount", "deal", "offer", "coupon", "promo", "voucher",
    "free shipping", "free delivery", "limited time", "last chance", "ends tonight",
    "black friday", "cyber monday", "exclusive", "save up to", "shop now", "new arrivals",
    "clearance", "bogo", "buy one",
]
UPDATE_WORDS = [
    "security alert", "sign-in", "sign in", "new login", "verify", "verification",
    "password", "your account", "notification", "reminder", "update", "updated",
    "terms of service", "privacy policy", "confirm your", "one-time code", "otp",
    "activity", "alert", "welcome to",
]
AUTOMATED_SENDER = re.compile(
    r"(no-?reply|do-?not-?reply|notifications?|alerts?|mailer|bounce|updates?|info|news|support|hello)@",
    re.I)


def _has(text, words):
    for w in words:
        if w in text:
            return w
    return None


def classify(m):
    """m: normalized message. Returns (category, reason)."""
    if m["folder"] == "deleted":
        return "Deleted Mail", "In Deleted Items / Trash"
    if m["folder"] == "junk":
        return "Junk", "In your Junk / Spam folder"

    h = m.get("headers") or {}
    subject = (m.get("subject") or "").lower()
    text = subject + " " + (m.get("preview") or "")[:400].lower()
    is_bulk = "list-unsubscribe" in h or "list-id" in h or \
        h.get("precedence", "").lower() in ("bulk", "list")
    automated = bool(AUTOMATED_SENDER.search(m.get("fromAddress") or "")) or is_bulk

    if m.get("importance") == "high" or m.get("flagged"):
        return "Priority", "Marked important or flagged"

    w = _has(text, TRANSACTION_WORDS)
    if w:
        return "Transactions", f'Mentions "{w}"'

    w = _has(subject, PROMO_WORDS) or (is_bulk and _has(text, PROMO_WORDS))
    if w:
        return "Promotions", f'Mentions "{w}"'

    if is_bulk:
        return "Mailing List", "Newsletter / list email (has unsubscribe header)"

    if automated:
        w = _has(text, UPDATE_WORDS)
        return "Updates", "Automated sender" + (f', mentions "{w}"' if w else "")

    if _has(subject, UPDATE_WORDS) and m.get("focused") == "other":
        return "Updates", "Notification-style email"

    return "Priority", "From a person" + (" (Outlook Focused)" if m.get("focused") == "focused" else "")
