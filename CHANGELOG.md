<p align="center">
  <img src="assets/logo.png" alt="MailMaster logo" width="96">
</p>

# Changelog

All notable changes to MailMaster are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [1.2.1] - 2026-11-05
### Added
- **Unclassified** category for emails that match no other rule, such as automated emails with no clear topic, or emails Outlook files under "Other".
- **Settings → Emails to load per account**: choose how many Inbox, Junk and Deleted emails to load (100 up to 5,000, or **Max** for everything). Deleted Mail is no longer capped at 100.
- **Paste** buttons on every account field, plus **Paste all settings** to fill email, username, IMAP/SMTP servers and password from copied text in one go.
- **Use saved password**: finds an account's password already saved on the computer (Mac Keychain or Windows Credential Manager). The computer asks you to approve with your password or Touch ID first.
- Username, IMAP and SMTP settings can now be edited for Gmail, iCloud and Yahoo too, under **Server settings**.

### Changed
- **Microsoft sign-in opens in your normal web browser**, so a Microsoft / Outlook login you already have there is reused and you just pick your account. MailMaster picks up the new account automatically.
- Cmd+V, Cmd+C, Cmd+X and Cmd+A now always work in the Mac app window.
- Very large deletes on Gmail/IMAP are sent in batches of 500.

### Security
- The local MailMaster server now only accepts changes from MailMaster's own window. This stops websites open in your browser from triggering actions on it.

## [1.2.0] - 2026-11-05
### Added
- **Desktop app** for Mac (Apple chip and Intel) and Windows. It opens in its own window, and no Python or setup is needed.
- Microsoft sign-in is built in, so people just click **Accounts → Outlook** and sign in.
- Each person's accounts are stored in their own app-data folder. Passwords go in the macOS Keychain or Windows Credential Manager.
- Web links (unsubscribe pages, "Open" in Gmail, help links) open in the normal browser.
- Automatic builds and GitHub Releases, with a start-up check of every build.
- Automated tests for sorting, unsubscribing, IMAP handling and the main actions.
- New MailMaster logo, used for the app icon, favicon, window header and docs.

### Changed
- Microsoft sign-in no longer uses a client secret (desktop/public client). This fixes the `AADSTS7000215 invalid client secret` sign-in error.
- Confirmation prompts are now MailMaster's own dialogs instead of browser pop-ups.
- Interface accent colours now match the logo (cyan, blue and violet).

## [1.1.0] - 2026-11-05
### Added
- **Deleted Mail** category showing each account's Deleted Items / Trash. Deleting from it removes emails permanently.
- **Group by sender** in every category.
- **Bulk unsubscribe**: tick several emails or senders, then click **Unsubscribe**. Results are listed per sender.
- Yellow envelope icon, yellow browser tab colour (Safari), and the version number shown in the app.

## [1.0.0] - 2026-11-05
### Added
- Local web app (http://localhost:3500) for Outlook (Microsoft Graph), Gmail, iCloud, Yahoo and other IMAP accounts.
- Sorting into Priority, Transactions, Updates, Promotions, Mailing List and Junk.
- Delete single, selected or all emails from a sender. Unsubscribe via one-click, email or link.
- All-accounts view with an account filter, and a demo mode with sample emails.
