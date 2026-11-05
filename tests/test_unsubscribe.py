import unsubscribe as u


def test_one_click():
    o = u.options({"list-unsubscribe": "<https://x.com/u>, <mailto:u@x.com>",
                   "list-unsubscribe-post": "List-Unsubscribe=One-Click"})
    assert o["one_click_url"] == "https://x.com/u" and o["mailto"] == "mailto:u@x.com"
    assert u.method(o) == "one-click"


def test_methods():
    assert u.method(u.options({"list-unsubscribe": "<mailto:u@x.com?subject=stop>"})) == "email"
    assert u.method(u.options({"list-unsubscribe": "<https://x.com/u>"})) == "link"
    assert u.options({}) is None


def test_blocks_private_addresses():
    assert not u._is_public_host("http://127.0.0.1/x")
    assert not u._is_public_host("http://192.168.1.10/x")
    assert not u._is_public_host("http://localhost/x")


def test_mailto_sent_and_link_fallback():
    sent = []
    r = u.perform({"one_click_url": None, "http_url": None, "mailto": "mailto:u@x.com?subject=stop"},
                  lambda to, s, b: sent.append((to, s)))
    assert r["status"] == "done" and sent == [("u@x.com", "stop")]
    r = u.perform({"one_click_url": None, "http_url": "https://x.com/u", "mailto": None}, None)
    assert r["status"] == "open_link" and r["url"] == "https://x.com/u"
