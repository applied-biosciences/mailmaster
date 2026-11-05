"""End-to-end API checks in demo mode (sample accounts, no network)."""
import collections

import pytest

import app as A


@pytest.fixture()
def client():
    A.STORE.clear()
    A.demo_data._STATE.clear()
    return A.app.test_client()


def counts(c):
    return collections.Counter(m["category"] for m in c.get("/api/summary").json["items"])


def test_page_and_ping(client):
    assert b"MailMaster v" in client.get("/").data
    assert client.get("/api/ping").json["app"] == "MailMaster"


def test_summary(client):
    d = client.get("/api/summary").json
    assert len(d["accounts"]) == 3 and "Deleted Mail" in d["categories"]
    assert counts(client)["Deleted Mail"] == 2


def test_delete_goes_to_deleted_mail_then_forever(client):
    client.get("/api/summary")  # the app always loads mail before deleting
    r = client.post("/api/delete", json={"ids": ["demo-gmail|inbox:0"]}).json
    assert r["deleted"] == ["demo-gmail|inbox:0"]
    assert "Dinner on Saturday?" in [m["subject"] for m in r["trash"]["demo-gmail"]]
    new_id = next(m["id"] for m in r["trash"]["demo-gmail"] if m["subject"] == "Dinner on Saturday?")
    r = client.post("/api/delete", json={"ids": [new_id]}).json
    assert r["deleted"] == [new_id] and counts(client)["Deleted Mail"] == 2


def test_bulk_unsubscribe(client):
    ids = [m["id"] for m in client.get("/api/summary").json["items"] if m["unsubscribe"]]
    r = client.post("/api/unsubscribe/bulk", json={"ids": ids, "deleteAll": True}).json
    statuses = {x["sender"]: x["status"] for x in r["results"]}
    assert statuses == {"hello@news.example.com": "done", "deals@shop.example.com": "done",
                        "noreply@medium.com": "open_link"}
    assert len(r["deleted"]) == 5 and counts(client)["Mailing List"] == 0


def test_open_url_only_web_links(client, monkeypatch):
    opened = []
    monkeypatch.setattr(A.webbrowser, "open", opened.append)
    assert client.post("/api/open-url", json={"url": "file:///etc/passwd"}).status_code == 400
    assert client.post("/api/open-url", json={"url": "https://example.com"}).json["ok"]
    assert opened == ["https://example.com"]
