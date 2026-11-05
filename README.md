<p align="center">
  <img src="assets/logo.png" alt="MailMaster logo" width="160">
</p>

<h1 align="center">MailMaster</h1>

<p align="center">
  <a href="../../releases/latest"><b>Download</b></a> ·
  <a href="#install">Install</a> ·
  <a href="#add-your-accounts">Add accounts</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

**One app to clean up all your email accounts**: Outlook / Hotmail / Microsoft 365, Gmail, iCloud, Yahoo and any IMAP account, together in one window.

- Sorts mail into **Priority, Transactions, Updates, Promotions, Mailing List, Unclassified, Junk, Deleted Mail**
- Shows all accounts together or one at a time (each email is tagged with its account)
- **Group by sender** in any category
- Delete one, selected, or all emails from a sender (to Deleted Mail, or permanently)
- **Unsubscribe** from mailing lists, one at a time or in bulk

Your mail stays on your computer. MailMaster connects directly to each email provider; there is no MailMaster server.

---

## Install

Download the latest version from the **[Releases](../../releases/latest)** page.

| Your computer | Download |
|---|---|
| Mac with Apple chip (M1, M2, M3, M4…) | `MailMaster-…-mac-apple-silicon.dmg` |
| Older Mac with Intel chip | `MailMaster-…-mac-intel.dmg` |
| Windows 10 / 11 | `MailMaster-…-windows.zip` |

Not sure which Mac you have? Apple menu → **About This Mac** → look at "Chip".

### Mac
1. Open the `.dmg` and drag **MailMaster** into **Applications**.
2. Open MailMaster from Applications. The first time, macOS says it can't verify the developer:
   - Click **Done**, then go to **System Settings → Privacy & Security**, scroll down and click **Open Anyway** next to MailMaster.
   - (Older macOS: right-click MailMaster → **Open** → **Open**.)
3. From then on it opens normally.

### Windows
1. Unzip the download and move `MailMaster.exe` somewhere handy (for example your Desktop).
2. Double-click it. If Windows shows **"Windows protected your PC"**, click **More info → Run anyway**.

---

## Add your accounts
Click **Accounts** in the top-right corner.

| Account | What you need |
|---|---|
| **Outlook / Hotmail / Microsoft 365** | Click **Outlook**: sign-in opens in your web browser. If you're already signed in to Microsoft there, just pick your account. Work accounts: your IT team may need to approve MailMaster once. |
| **Gmail** | An **app password**: turn on 2-Step Verification, then create one at <https://myaccount.google.com/apppasswords> |
| **iCloud** | An **app-specific password**: <https://account.apple.com> → Sign-In and Security → App-Specific Passwords |
| **Yahoo** | An **app password**: Yahoo Account Security → Generate app password |
| **Other (IMAP)** | Your provider's IMAP and SMTP server names (listed on their help pages) |

Tips when adding Gmail, iCloud, Yahoo or other accounts:
- **Paste** buttons sit next to every field, and **Paste all settings** fills email, username, servers and password from copied text in one go.
- **Use saved password** finds the password if it's already saved on your computer (for example by Apple Mail). Your Mac or PC asks you to approve first.
- **Server settings** lets you change the username, IMAP and SMTP details for any provider.

You can add as many accounts as you like. **Accounts → Remove** disconnects one. Your emails are not touched.

## Using it
- Click a category card to see its emails. Use the account menu (top right) to show one account.
- Tick emails, then **Delete** or **Unsubscribe (N senders)**. Turn on **Group by sender** to tick whole senders at once.
- **Delete** moves emails to **Deleted Mail**. Deleting from Deleted Mail removes them for good. Gmail empties its Trash after 30 days.
- Some senders need you to confirm on their website. MailMaster shows a **Confirm on their site** button for those.
- **Refresh** re-reads all accounts.
- **Settings** sets how many emails load per account for Inbox, Junk and Deleted Mail, from 100 up to **Max** (everything).
- **Unclassified** holds emails that match no other rule.

## Privacy & where things are stored
Everything stays on your computer:
- **Mac:** `~/Library/Application Support/MailMaster/`
- **Windows:** `%APPDATA%\MailMaster\`

That folder holds your account list (`accounts.json`), Microsoft sign-ins (`token_cache.json`), your settings (`settings.json`) and a log (`mailmaster.log`). Gmail/iCloud/Yahoo/IMAP passwords are kept in the **macOS Keychain** or **Windows Credential Manager**.

By default MailMaster loads the latest 300 inbox emails per account, plus 100 each from Junk and Deleted. To change this, use **Settings** (up to **Max**). Your choice is saved in `settings.json` in that folder.

## Troubleshooting
- **"Port 3500 is being used by another program":** close the other program, or put `PORT=3600` in a `.env` file in the data folder. If you change the port, Microsoft sign-in needs that redirect address added too (see Maintainers).
- **The window doesn't open (Windows):** run `MailMaster.exe --browser` to use your web browser instead.
- **A Gmail/iCloud/Yahoo account won't connect:** use an app password, not your normal password.
- **Something else:** send the `mailmaster.log` file from the data folder above.

---

## Maintainers

### One-time setup: Microsoft sign-in
Outlook accounts need a Microsoft "app registration". It's free, and it's done once for everyone who uses MailMaster.

1. <https://entra.microsoft.com> → **App registrations** → **New registration**
   - Name `MailMaster`; account types: **Accounts in any organizational directory and personal Microsoft accounts**
2. **Authentication** → **Add a platform** → **Mobile and desktop applications** → custom redirect URI `http://localhost:3500/auth/callback`. Set **Allow public client flows** to **Yes**. **No client secret is needed.**
3. **API permissions** → Microsoft Graph → Delegated → `Mail.ReadWrite`, `Mail.Send` (plus the default `User.Read`).
4. The **Application (client) ID** goes in `mailmaster/build_info.py` (already set to MailMaster's ID). It is not a secret. To use a different ID for a build without changing the code, add a repository variable `MS_CLIENT_ID` (**Settings → Secrets and variables → Actions → Variables**).

### Making a release
1. Update `VERSION` in `mailmaster/version.py` and add a section to `CHANGELOG.md`.
2. Commit to `main`.
3. Go to **Actions → Test & build → Run workflow**, tick **Publish release**, then click **Run workflow**.
4. GitHub Actions tests the code, builds the Mac (Apple chip + Intel) and Windows apps, and checks that each one starts. It then publishes them on the Releases page as `v<version>` (about 15 minutes). If any build fails, nothing is published.

To build without releasing, run it with **Publish release** unticked. The files appear under that run's **Artifacts**. Pushing a tag such as `v1.2.0` also releases.

Note: on a private repo, macOS build minutes count 10× against the organisation's Actions allowance. That's why apps are only built for tags and manual runs.

### Running from source
```
bash run.sh            # macOS / Linux   (add --browser to use your web browser)
run.bat                # Windows
```
Optional settings go in a `.env` file at the repo root (see `.env.example`). `DEMO_MODE=1` shows sample accounts.

### Tests
```
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

### Project layout
```
mailmaster/
  desktop.py        app entry point: starts the local server, opens the window
  app.py            web server and API
  ms_provider.py    Outlook / Microsoft 365 (Microsoft Graph)
  imap_provider.py  Gmail, iCloud, Yahoo, other IMAP
  classifier.py     sorting rules (edit the keyword lists to tune)
  settings.py       per-person settings (emails to load)
  saved_passwords.py  'Use saved password' (Keychain / Credential Manager)
  unsubscribe.py    List-Unsubscribe handling (one-click, email, link)
  accounts.py       stored accounts and passwords (Keychain / Credential Manager)
  templates/, static/   the interface
mailmaster.spec     PyInstaller build recipe
.github/workflows/build.yml   tests, builds and releases
```
