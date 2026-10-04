# Validation report

Completed on 2026-10-04:

- 17 pytest cases passed against isolated SQLite databases.
- JavaScript syntax checked with `node --check static/app.js`.
- Python files compiled successfully.

Not completed:

- Browser UI automation: Chromium download failed in the build environment, so no visual/mobile browser validation is claimed.
- Live Telegram menu/webhook/authentication: requires the owner's real token and HTTPS deployment.
- PostgreSQL integration: supported by SQLAlchemy/psycopg configuration, but not exercised against a live PostgreSQL instance here.

Before everyday use, deploy and check: /id and allowlist, /start menu, add one KHR expense and one USD income, edit/delete, monthly budget, CSV export, Khmer/English and your phone's layout. Ensure data survives a service restart and your database backup can be restored.

Admin approval tests cover unauthenticated access rejection, admin-only actions, self-approval rejection, repeat/stale callbacks, notification throttling, /requests recovery, persisted approvals across app restart, per-user transaction isolation and /id before initial admin setup. Telegram HTTP calls were mocked; live delivery still needs real deployment verification.
