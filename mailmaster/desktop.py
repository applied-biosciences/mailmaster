"""MailMaster desktop app: starts the local server and shows it in its own window.

Falls back to the normal web browser if a native window isn't available
(or when started with --browser / MAILMASTER_BROWSER=1).
"""
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

import config

URL = f"http://localhost:{config.PORT}"


def _setup_logging():
    """A packaged (windowed) app has no console, so send output to a log file in the data folder."""
    if config.FROZEN or sys.stdout is None or sys.stderr is None:
        log = open(config.LOG_FILE, "a", buffering=1, encoding="utf-8")  # noqa: SIM115
        sys.stdout = sys.stderr = log
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


class ClipboardApi:
    """Copy/paste for the app window (exposed to the page as window.pywebview.api).
    The macOS web view doesn't always pass Cmd+V/Cmd+C through, so the page asks Python instead."""

    def read_clipboard(self):
        try:
            if sys.platform == "darwin":
                return subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5).stdout
            if os.name == "nt":
                r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                                   capture_output=True, text=True, timeout=5,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return r.stdout.rstrip("\r\n")
        except Exception as e:  # noqa: BLE001
            logging.warning("Clipboard read failed: %s", e)
        return ""

    def write_clipboard(self, text):
        try:
            if sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=text, text=True, timeout=5)
                return True
            if os.name == "nt":
                subprocess.run(["clip"], input=text, text=True, timeout=5,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return True
        except Exception as e:  # noqa: BLE001
            logging.warning("Clipboard write failed: %s", e)
        return False


def _ping():
    """Returns True if a MailMaster server already answers on our port."""
    try:
        with urllib.request.urlopen(f"{URL}/api/ping", timeout=1) as r:
            return json.load(r).get("app") == config.APP_NAME
    except Exception:  # noqa: BLE001
        return False


def _port_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", config.PORT))
            return True
        except OSError:
            return False


def _start_server():
    from werkzeug.serving import make_server
    from app import app

    server = make_server("127.0.0.1", config.PORT, app, threaded=True)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    for _ in range(100):  # wait up to 10 s
        if _ping():
            break
        time.sleep(0.1)
    return t


def _show_error(message):
    logging.error(message)
    try:
        import webview
        webview.create_window("MailMaster", html=f"<body style='font:15px system-ui;padding:30px'>"
                                                 f"<h3>MailMaster can't start</h3><p>{message}</p></body>",
                              width=520, height=260)
        webview.start()
    except Exception:  # noqa: BLE001
        print(message)


def main():
    _setup_logging()
    logging.info("Starting %s v%s (data: %s)", config.APP_NAME, config.VERSION, config.DATA_DIR)

    server_thread = None
    if not _ping():
        if not _port_free():
            _show_error(f"Port {config.PORT} is being used by another program. Close it and try again.")
            return 1
        server_thread = _start_server()

    use_browser = "--browser" in sys.argv or os.getenv("MAILMASTER_BROWSER") == "1"
    if not use_browser:
        try:
            import webview
            webview.create_window(f"{config.APP_NAME} v{config.VERSION}", URL, js_api=ClipboardApi(),
                                  width=1280, height=860, min_size=(900, 600))
            webview.start()
            return 0  # window closed -> quit (server thread is a daemon)
        except Exception as e:  # noqa: BLE001
            logging.warning("Native window unavailable (%s); using the web browser instead.", e)

    webbrowser.open(URL)
    if server_thread:
        print(f"MailMaster is running at {URL}. Press Ctrl+C to stop.")
        try:
            while server_thread.is_alive():
                server_thread.join(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
