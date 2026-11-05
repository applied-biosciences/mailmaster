"""Unsubscribe using the standard List-Unsubscribe headers (RFC 2369 / RFC 8058)."""
import ipaddress
import re
import socket
from urllib.parse import urlparse, parse_qs, unquote
import requests


def options(headers):
    """Parse headers -> dict(one_click_url, http_url, mailto) or None."""
    raw = headers.get("list-unsubscribe", "")
    if not raw:
        return None
    links = re.findall(r"<([^>]+)>", raw) or [p.strip() for p in raw.split(",")]
    http_url = next((l for l in links if l.lower().startswith(("https://", "http://"))), None)
    mailto = next((l for l in links if l.lower().startswith("mailto:")), None)
    one_click = "list-unsubscribe=one-click" in headers.get("list-unsubscribe-post", "").lower()
    if not (http_url or mailto):
        return None
    return {"one_click_url": http_url if (one_click and http_url and http_url.lower().startswith("https://")) else None,
            "http_url": http_url, "mailto": mailto}


def method(opts):
    if not opts:
        return None
    if opts["one_click_url"]:
        return "one-click"
    if opts["mailto"]:
        return "email"
    return "link"


def _is_public_host(url):
    """Block requests to your own machine / private network (links come from untrusted emails)."""
    host = urlparse(url).hostname
    if not host:
        return False
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def _parse_mailto(m):
    p = urlparse(m)
    q = parse_qs(p.query)
    return unquote(p.path), q.get("subject", ["unsubscribe"])[0], q.get("body", ["unsubscribe"])[0]


def perform(opts, send_mail_fn):
    """Returns {"status": "done"|"open_link"|"failed", "message": str, "url"?: str}."""
    if opts.get("one_click_url"):
        url = opts["one_click_url"]
        if _is_public_host(url):
            try:
                r = requests.post(url, data={"List-Unsubscribe": "One-Click"}, timeout=15,
                                  allow_redirects=False, headers={"User-Agent": "MailMaster/1.0"})
                if r.status_code < 400:
                    return {"status": "done", "message": "Unsubscribed (one-click)."}
            except requests.RequestException:
                pass
    if opts.get("mailto"):
        to, subject, body = _parse_mailto(opts["mailto"])
        try:
            send_mail_fn(to, subject, body)
            return {"status": "done", "message": f"Unsubscribe email sent to {to}."}
        except Exception as e:  # noqa: BLE001
            if not opts.get("http_url"):
                return {"status": "failed", "message": f"Could not send unsubscribe email: {e}"}
    if opts.get("http_url"):
        return {"status": "open_link", "url": opts["http_url"],
                "message": "This sender needs you to confirm on their page. It has opened in a new tab."}
    return {"status": "failed", "message": "No unsubscribe option found."}
