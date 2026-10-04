# Validation — 2026-10-04

- 32 pytest cases passed using isolated SQLite databases.
- JavaScript syntax passed node --check.
- Chromium mobile viewport 390x844: signed Telegram data simulated; actual local Flask APIs used. Expense creation, savings goal creation, theme/language switching and home navigation succeeded, without JavaScript errors or horizontal overflow. Chart rendered with saved expense data. Error/retry screen also rendered on a simulated database failure.
- Browser environment lacked Khmer/emoji fonts; device font rendering needs a real phone check.

Not verified: live Telegram delivery/fullscreen, live Neon PostgreSQL, Render deployment, and real phone interaction. Telegram HTTP calls in backend tests are mocked.

Tests include auth, ownership, money precision, request deduplication, webhook secret, approval/revocation permissions, stale callbacks, admin views, savings goal version conflicts, period summaries and budget alert thresholds/delivery failures.

After deployment: send /id, configure ADMIN_USER_ID, send /start and /admin; verify access requests from another account, KHR/USD records, budgets and notifications, goals, export and persistence after restarting the service.
