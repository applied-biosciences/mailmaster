"""IMAP code against a simulated Gmail server."""
import imaplib

import pytest

import classifier
import imap_provider as ip

H1 = (b"From: =?UTF-8?Q?Caf=C3=A9_Deals?= <deals@shop.example.com>\r\nSubject: 30% off this weekend\r\n"
      b"Date: Wed, 04 Nov 2026 10:00:00 +0000\r\nMessage-ID: <abc@shop>\r\n"
      b"List-Unsubscribe: <https://shop.example.com/u>\r\nList-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n\r\n")
T1 = b"--b1\r\nContent-Type: text/plain\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\nBig savings on every=\r\nthing.\r\n"
H2 = b"From: Omar <omar@gmail.com>\r\nSubject: Lunch?\r\nDate: Thu, 05 Nov 2026 08:00:00 +0000\r\n\r\n"
T2 = b"<html><body><p>Free tomorrow?</p></body></html>"
H3 = b"From: Spammy <x@spam.biz>\r\nSubject: WIN\r\nDate: Thu, 05 Nov 2026 01:00:00 +0000\r\n\r\n"


class FakeIMAP:
    log = []

    def __init__(self, host, port, timeout=None):
        self.capabilities = ("IMAP4REV1", "MOVE", "UIDPLUS")
        self.sel = None

    def login(self, user, pw):
        if pw != "secret":
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        return "OK", [b""]

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Junk) "/" "[Gmail]/Spam"',
                      b'(\\HasNoChildren \\Trash) "/" "[Gmail]/Trash"']

    def select(self, f, readonly=False):
        self.sel = f
        FakeIMAP.log.append(("select", f))
        return "OK", [b"1"]

    def uid(self, cmd, *a):
        FakeIMAP.log.append((cmd,) + a)
        if cmd == "SEARCH":
            return "OK", [b"10 11" if self.sel == '"INBOX"' else b"7"]
        if cmd == "FETCH":
            if self.sel == '"INBOX"':  # items deliberately out of order for message 2
                return "OK", [(b"1 (UID 10 FLAGS (\\Seen) BODY[HEADER.FIELDS (FROM)] {%d}" % len(H1), H1),
                              (b" BODY[TEXT]<0> {%d}" % len(T1), T1), b")",
                              (b"2 (UID 11 BODY[TEXT]<0> {%d}" % len(T2), T2),
                              (b" BODY[HEADER.FIELDS (FROM)] {%d}" % len(H2), H2), b" FLAGS (\\Flagged))"]
            return "OK", [(b"1 (UID 7 FLAGS () BODY[HEADER.FIELDS (FROM)] {%d}" % len(H3), H3),
                          (b" BODY[TEXT]<0> {2}", b"hi"), b")"]
        return "OK", [b""]

    def expunge(self):
        return "OK", [b""]

    def logout(self):
        return "BYE", [b""]


ACC = {"id": "imap-x", "type": "imap", "provider": "gmail", "email": "me@gmail.com", "imap_host": "imap.gmail.com",
       "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 465, "password": "secret", "password_in": "file"}


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeIMAP)
    FakeIMAP.log.clear()


def test_wrong_password():
    with pytest.raises(imaplib.IMAP4.error):
        ip.test_login(ACC, "wrong")


def test_fetch_and_classify():
    msgs = {m["id"]: m for m in ip.fetch(ACC, 300, 100, 100)}
    promo, lunch = msgs["inbox:10"], msgs["inbox:11"]
    assert promo["fromName"] == "Café Deals" and promo["preview"] == "Big savings on everything."
    assert classifier.classify(promo)[0] == "Promotions"
    assert lunch["flagged"] and not lunch["isRead"] and lunch["preview"] == "Free tomorrow?"
    assert classifier.classify(lunch)[0] == "Priority"
    assert classifier.classify(msgs["junk:7"])[0] == "Junk"
    assert classifier.classify(msgs["deleted:7"])[0] == "Deleted Mail"
    assert "rfc822msgid" in promo["webLink"]


def test_delete_moves_to_trash():
    msgs = ip.fetch(ACC, 300, 0, 0)
    assert ip.delete(ACC, msgs[:1], permanent=False) == ["inbox:10"]
    assert ("MOVE", "10", '"[Gmail]/Trash"') in FakeIMAP.log


def test_delete_from_trash_is_permanent():
    trash = ip.fetch_deleted(ACC, 10)
    assert ip.delete(ACC, trash, permanent=False) == ["deleted:7"]
    assert ("STORE", "7", "+FLAGS.SILENT", r"(\Deleted)") in FakeIMAP.log
    assert ("EXPUNGE", "7") in FakeIMAP.log
