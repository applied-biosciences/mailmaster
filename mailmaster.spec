# PyInstaller build recipe for MailMaster.
#   macOS   -> dist/MailMaster.app
#   Windows -> dist/MailMaster.exe (single file)
# Build:  pyinstaller mailmaster.spec --noconfirm
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(SPECPATH)  # noqa: F821  (provided by PyInstaller)
SRC = os.path.join(ROOT, "mailmaster")
sys.path.insert(0, SRC)
from version import APP_NAME, VERSION  # noqa: E402

hidden = [
    "app", "auth", "graph", "ms_provider", "imap_provider", "accounts", "classifier",
    "unsubscribe", "config", "demo_data", "build_info", "version", "settings", "saved_passwords",
] + collect_submodules("keyring.backends")

a = Analysis(  # noqa: F821
    [os.path.join(SRC, "desktop.py")],
    pathex=[SRC],
    datas=[(os.path.join(SRC, "templates"), "templates"), (os.path.join(SRC, "static"), "static")],
    hiddenimports=hidden,
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

if sys.platform == "darwin":
    exe = EXE(  # noqa: F821
        pyz, a.scripts, [], exclude_binaries=True, name=APP_NAME,
        console=False, icon=os.path.join(ROOT, "assets", "icon.icns"),
    )
    coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)  # noqa: F821
    app = BUNDLE(  # noqa: F821
        coll,
        name=f"{APP_NAME}.app",
        icon=os.path.join(ROOT, "assets", "icon.icns"),
        bundle_identifier="com.appliedbiosciences.mailmaster",
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            # The app window shows MailMaster's own local page at http://localhost
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        },
    )
else:
    exe = EXE(  # noqa: F821
        pyz, a.scripts, a.binaries, a.datas, [], name=APP_NAME,
        console=False, upx=False, icon=os.path.join(ROOT, "assets", "icon.ico"),
    )
