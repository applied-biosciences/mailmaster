@echo off
rem Run MailMaster from source (Windows). Usage: run.bat [--browser]
cd /d "%~dp0"
if not exist .venv (
  echo Setting up (about a minute)...
  py -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install -q -r requirements.txt
)
.venv\Scripts\python mailmaster\desktop.py %*
