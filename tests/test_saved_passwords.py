import subprocess
import types

import saved_passwords as sp


def test_mac_keychain_lookup(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        found = cmd[1] == "find-internet-password" and "imap.mail.me.com" in cmd and "me@icloud.com" in cmd
        return types.SimpleNamespace(returncode=0 if found else 44, stdout="abcd-efgh-ijkl\n" if found else "")

    monkeypatch.setattr(sp.sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", fake_run)
    pw, where = sp.find("me@icloud.com", "", ["imap.mail.me.com", "smtp.mail.me.com"])
    assert pw == "abcd-efgh-ijkl" and "Keychain" in where
    assert calls[0][:2] == ["security", "find-internet-password"] and "-w" in calls[0]


def test_not_found_message(monkeypatch):
    monkeypatch.setattr(sp.sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(returncode=44, stdout=""))
    pw, msg = sp.find("me@gmail.com", "", ["imap.gmail.com"])
    assert pw is None and "No saved password" in msg


def test_needs_email():
    assert sp.find("", "", ["imap.gmail.com"])[0] is None
