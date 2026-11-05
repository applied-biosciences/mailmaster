"""Writes mailmaster/build_info.py with the Microsoft app (client) ID for a release build.

Usage:  python scripts/write_build_info.py <client-id>
An empty ID is allowed (the build then supports Gmail/iCloud/Yahoo/IMAP only).
"""
import os
import re
import sys

client_id = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
if client_id and not re.fullmatch(r"[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", client_id):
    sys.exit(f"MS_CLIENT_ID doesn't look like a Microsoft app ID: {client_id!r}")

path = os.path.join(os.path.dirname(__file__), "..", "mailmaster", "build_info.py")
with open(path, "w", encoding="utf-8") as f:
    f.write("# Generated during the build. The Microsoft app (client) ID is not a secret.\n")
    f.write(f'CLIENT_ID = "{client_id}"\n')
print("Microsoft app ID:", "set" if client_id else "NOT SET (Outlook accounts disabled in this build)")
