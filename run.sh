#!/bin/bash
# Run MailMaster from source (macOS / Linux). Usage: bash run.sh [--browser]
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Setting up (about a minute)..."
  python3 -m venv .venv || { echo "Python 3 not found. Install it from https://www.python.org/downloads/"; exit 1; }
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -r requirements.txt || exit 1
fi
.venv/bin/python mailmaster/desktop.py "$@"
