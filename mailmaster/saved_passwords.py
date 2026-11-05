"""Looks up a password already saved on this computer for a mail account.

macOS: searches the Keychain (passwords saved by Apple Mail and other apps). macOS asks the person
to approve with their Mac password or Touch ID before releasing it.
Windows: searches Windows Credential Manager for entries saved under the mail server name.
"""
import os
import subprocess
import sys


def _mac_lookup(hosts, accounts):
    for host in hosts:
        for acct in accounts:
            for kind in ("find-internet-password", "find-generic-password"):
                try:
                    r = subprocess.run(["security", kind, "-s", host, "-a", acct, "-w"],
                                       capture_output=True, text=True, timeout=120)
                except (OSError, subprocess.TimeoutExpired):
                    continue
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.rstrip("\r\n"), f"your Mac's Keychain ({host})"
    return None, None


def _windows_lookup(hosts, accounts):
    try:
        import keyring
    except ImportError:
        return None, None
    for host in hosts:
        for acct in accounts:
            try:
                pw = keyring.get_password(host, acct)
            except Exception:  # noqa: BLE001
                pw = None
            if pw:
                return pw, f"Windows Credential Manager ({host})"
    return None, None


def find(email, username, hosts):
    """Returns (password, where) or (None, message)."""
    hosts = [h for h in dict.fromkeys(h.strip().lower() for h in hosts if h and h.strip())]
    accts = [a for a in dict.fromkeys(a.strip() for a in (email, username) if a and a.strip())]
    if not hosts or not accts:
        return None, "Enter the email address (and server for Other accounts) first."
    if sys.platform == "darwin":
        pw, where = _mac_lookup(hosts, accts)
        place = "your Mac's Keychain"
    elif os.name == "nt":
        pw, where = _windows_lookup(hosts, accts)
        place = "Windows Credential Manager"
    else:
        return None, "Looking up saved passwords isn't available on this computer."
    if pw:
        return pw, where
    return None, (f"No saved password for {accts[0]} was found in {place}. "
                  "Enter it yourself (Gmail, iCloud and Yahoo need an app password).")
