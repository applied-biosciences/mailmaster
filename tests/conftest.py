import os
import sys
import tempfile

# Settings must be in place before the app modules are imported.
os.environ["DEMO_MODE"] = "1"
os.environ["MAILMASTER_DATA"] = tempfile.mkdtemp(prefix="mailmaster-test-")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mailmaster"))
