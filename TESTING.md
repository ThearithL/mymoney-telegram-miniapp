# Validation — 2026-10-04

## Current build

- 45 pytest tests passed using isolated SQLite databases. Includes auth, per-user ownership, money precision, idempotency, approval/revocation, goals, summary periods, budget alerts, Telegram menu open/close and bulk deletion.
- Bulk deletion tests cover missing auth, foreign entries, wrong confirmation, foreign tokens, expiry, single use, replaced previews and preservation of later entries/goals.
- Browser test source: tests/ui_smoke.py. Uses simulated signed Telegram initData and a real local Flask API with temporary SQLite. No real Telegram or user data is modified.
- Browser matrix: 320x568, 360x800, 390x844, 768x1024, 844x390, 1280x800, 1920x1080. Both interface languages, light/dark themes, navigation, donut percentages, edit, selected deletion, cancel confirmation, delete-all and another user's data isolation are exercised.
- Calculator UI was removed.

To rerun backend: pip install -r requirements-dev.txt; python -m pytest -q.
Optional browser check: pip install playwright==1.51.0; python -m playwright install chromium; python tests/ui_smoke.py.

Not verified: live Render/Neon, actual Telegram delivery/fullscreen, native phone keyboards and iOS WebKit. Khmer glyph rendering depends on device fonts; the browser environment does not include Khmer fonts.

After deployment, send /start, /closemenu and /menu, then verify your real phone's layout and create/edit/delete a disposable entry. Keep Neon DATABASE_URL unchanged.

Latest feature validation: added tests for trash/restore/purge, photo authorization/validation and retention through restore, profile validation/isolation, category limits, previous-year monthly comparison and changes after restoration. Browser integration additionally exercised photo upload/display, restoration with its photo, profile saving and the 90% category warning at 320px. Tests use synthetic data only.

Profile/UI iteration also covers personal favorite create/list/delete, twelve-favorite cap and client-side amount masking preference. Backend tests now total 47. Live browser automation is unavailable in this restricted run; the smoke script remains for local execution.
