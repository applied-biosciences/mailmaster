"""Writes mailmaster/build_info.py with the Microsoft app (client) ID for a release build.

Usage:  python scripts/write_build_info.py [client-id]
With no ID, the ID already in mailmaster/build_info.py is kept.
"""
import os
import re
import sys

client_id = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
path = os.path.join(os.path.dirname(__file__), "..", "mailmaster", "build_info.py")
if not client_id:
    current = re.search(r'CLIENT_ID = "([^"]*)"', open(path, encoding="utf-8").read())
    print("Microsoft app ID:", "built in" if current and current.group(1) else "NOT SET (Outlook accounts disabled)")
    sys.exit(0)
if client_id and not re.fullmatch(r"[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", client_id):
    sys.exit(f"MS_CLIENT_ID doesn't look like a Microsoft app ID: {client_id!r}")

with open(path, "w", encoding="utf-8") as f:
    f.write("# Generated during the build. The Microsoft app (client) ID is not a secret.\n")
    f.write(f'CLIENT_ID = "{client_id}"\n')
print("Microsoft app ID: set from MS_CLIENT_ID")
