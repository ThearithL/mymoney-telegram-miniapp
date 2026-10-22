# លុយខ្ញុំ · MyMoney Telegram Mini App — Dashboard, goals and admin update

A complete, self-hosted personal expense tracker: Python/Flask API + Telegram bot webhook + responsive vanilla HTML/CSS/JavaScript. No frontend build step. Start with `RENDER_SETUP_KH.md` for the simplest Render + Neon deployment and owner bootstrap.

## Included

- Telegram persistent menu, quick expense/income buttons and inline Mini App launch.
- Daily expense chart with data table; today/week/month summaries in app and bot.
- Savings goals with progress and estimated finish time; add or withdraw savings with a separate dated history, once-per-goal 50/80/100% Telegram alerts, and edit/delete. Completed goals can be hidden and restored without losing their savings history. Savings movements do not create expense or income transactions.
- Quick-entry keypad screen for Add expense / Add income: ៛/$ toggle, big amount display, cash/bank, date and need/want pills, category and memo chips (recent notes + presets + write your own), custom 0–9 / 00 (or decimal point for USD) keypad and a bottom save bar. It submits through the same form and API as before; editing, favorites, quick buttons and itemised expenses still use the full form (use **More options** on the keypad to switch).
- Light/dark/system themes, quick-entry drafts, loading animations and retry messages.
- Budget alerts at 80% and 100% in app and Telegram.
- Set a monthly expense cap for the selected month and display currency; update it any time, with an in-app progress bar and Telegram warning.
- Set separate monthly spending caps for needs and wants; each shows a progress bar and an in-app warning near or over the limit.
- Mark each expense as a need or a want. See the split for the selected month and year.
- Yearly report: income, expenses, net, top spending category, needs/wants split and month-by-month chart. USD/KHR are combined with the saved display rate.
- Telegram menu shortcuts open the monthly budget, yearly report and savings goals directly.
- Owner admin dashboard: USD/KHR monthly expense donut charts, user/access totals, user records, message history and admin audit.
- Owner can send a private Telegram message to a selected user and review the delivery history.
- Owner-only transaction CRUD in the Admin Console: create and edit a user's records; deletes go to that user's recoverable Trash.
- User CRUD in Admin Console: create/approve by Telegram ID or a previously observed @username, search/filter, edit a persistent admin display label, change access, or permanently erase a non-admin account and its app data after typing the exact ID. A keyed, non-reversible deletion marker prevents rejoining from a legacy allowlist; audit history remains anonymized. The owner account and admin accounts are protected.
- Admin password gate: a password hash configured in Render, 15-minute dashboard unlock, explicit Lock button, HttpOnly/SameSite cookies, and a database-backed 5-attempt/15-minute lockout. Telegram signed Mini App authentication is still required.
- Request access button, admin Approve/Reject buttons, persistent access decisions in Neon.
- `/id` works before approval; `/request` submits access; `/requests` recovers pending requests for the owner.
- `ADMIN_USER_ID` grants the owner access; nobody can claim admin through the UI.
- Fullscreen request with safe-area spacing on supported Telegram clients.
- Khmer/English interface; mobile navigation, light/dark system theme.
- Add income/expenses, built-in or personal categories, cash/bank label, date and optional note. Track personal borrowing/lending with due dates, paid status, private proof photos and an audit timeline showing added/updated values. Create up to 40 personal categories for income, expenses or both; rename or delete them in Settings. Deletion is blocked while a category is attached to saved data.
- Edit, confirmed delete, month/currency filters, history search and pagination.
- Monthly income minus expenses, category bars, monthly budgets, in-app budget warnings.
- KHR is stored as whole riel and USD as cents. The dashboard, history, charts, summaries and comparison combine both currencies using your saved display rate; each entry remains stored in its original currency. The default display rate is 4,000 KHR/USD and can be edited in Settings.
- CSV export of your own full history, with spreadsheet formula escaping.
- Server-side Telegram initData signature/age verification, user allowlist, per-user data isolation.
- Duplicate create retries reuse a request ID; SQLAlchemy supports SQLite and PostgreSQL.

**Scope:** This version implements the core tracker. Scheduled reminders, OCR, voice recognition, bank integration and account transfers are not included. The exchange rate is manually editable and used for display totals only; it is not a live market quote. The dashboard net figure is selected-month income minus expenses, not a verified bank balance. Cash/bank are labels only. CSV downloads may depend on Telegram client support; try Telegram Desktop if mobile download is blocked.

## 1. Create your Telegram bot

1. Open the official `@BotFather` in Telegram and send `/newbot`.
2. Choose its name and username. Keep the token private.
3. Install Python 3.12+ and extract this ZIP. Open a terminal in `mymoney-miniapp`.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))'
```

Put the generated random string in `WEBHOOK_SECRET`. Edit `.env` with your own values:

```dotenv
BOT_TOKEN=your_botfather_token
APP_URL=https://your-service.onrender.com
WEBHOOK_SECRET=your_generated_random_secret
ADMIN_USER_ID=your_numeric_personal_telegram_id
# Choose ONE: set a direct password, or use the optional hash below.
ADMIN_PASSWORD=choose_your_own_long_password
# ADMIN_PASSWORD_HASH=your_werkzeug_password_hash
FLASK_SECRET_KEY=your_random_64_character_secret
ALLOWED_USER_IDS=
DATABASE_URL=postgresql://user:password@host/database
```

Optional extra pre-approved IDs in ALLOWED_USER_IDS are comma-separated. If both ADMIN_USER_ID and ALLOWED_USER_IDS are empty, Mini App access is disabled until owner bootstrap. Approved users are stored in access_requests, not environment variables. Never commit `.env` or password hashes/secrets.

To choose a password directly, set `ADMIN_PASSWORD` in Render → Environment to the password you want, then save and redeploy. Keep the Render service private to your trusted users and use a long, unique password. The app compares direct passwords safely and never displays them. For stronger secret handling, you can instead leave `ADMIN_PASSWORD` empty and set `ADMIN_PASSWORD_HASH` to a Werkzeug password hash:

```powershell
.venv\Scripts\python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('New Admin password: ')))"
```

Set `FLASK_SECRET_KEY` to a separate random secret and keep it unchanged; it signs secure Admin sessions and keyed deletion markers. The password is required again after 15 minutes or when you press Lock. Five failed attempts lock Admin login for 15 minutes. Admin APIs require both valid Telegram Mini App authentication and the password unlock.

## 2. Deploy to Render with PostgreSQL

1. Put the extracted project files in your own GitHub repository (the directory containing `app.py` should be the service root).
2. Create a PostgreSQL database with a provider of your choice. Copy its connection URL. Configure the provider's required TLS options, e.g. `?sslmode=require` when required.
3. Create a Render **Web Service** from that repository.
4. Build command: `pip install -r requirements.txt`
5. Start command: `python setup_bot.py && gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60`
6. Add the environment variables above. Set `APP_URL` to the actual public HTTPS service URL, without a trailing slash. Set `PYTHON_VERSION` to `3.12.14` if using the included blueprint.
7. Health check path: `/health`. Deploy. Tables are created automatically for a new database.

`render.yaml` is also provided for Blueprint deployment; fill its prompted values. The blueprint does not provision a database or choose a service plan. Check the provider's current plan pricing, idle/sleep behavior, storage retention and backup policy before choosing it.

**Do not use SQLite on an ephemeral host filesystem.** Use external PostgreSQL for deployed data. SQLite is only the local default. CSV is an export, not a full database backup (budgets are excluded). Enable database backups and test restoration. The needs/wants feature adds its column to existing transaction tables automatically; other future schema changes may still need migrations because `create_all` does not migrate existing tables.

## 3. Connect Telegram to the deployed app

The updated Render Start Command runs setup_bot.py automatically. You can skip local setup below when using that command. For first setup, leave ADMIN_USER_ID and ALLOWED_USER_IDS empty, deploy, send /id to the bot, then place your own numeric ID in ADMIN_USER_ID and redeploy. Send /start once as admin so the bot can notify you.

### Optional local setup

On your computer, set `.env` to the same `BOT_TOKEN`, `APP_URL` and `WEBHOOK_SECRET` as the deployed service, then run:

```powershell
.venv\Scripts\python setup_bot.py
```

Linux/macOS: `.venv/bin/python setup_bot.py`.

The script registers the webhook, chat menu button and bot commands including `/start`, `/menu`, `/id`, `/summary` and `/allowance`. It replaces any existing webhook for this bot; use a dedicated bot, and do not run a polling bot with the same token.

**If you don't know your Telegram ID:** deploy initially with an empty `ALLOWED_USER_IDS`, run `setup_bot.py`, then send `/id` in your bot's private chat. Copy that numeric ID into Render's `ALLOWED_USER_IDS` environment variable and redeploy. The `/id` command works before access is allowed. For approval management, put your personal ID in ADMIN_USER_ID, not only in ALLOWED_USER_IDS.

Now send `/start` and tap **💰 Open MyMoney** or the chat menu button. Use a private bot chat. The app must be opened through Telegram for authenticated API access. Ordinary browser access shows the layout and an instruction to open Telegram; it does not bypass login.

## Telegram notifications for Render deploys

The Mini App checks Render's Deploy API when an external uptime monitor calls `/ops/render-deploy-watch/<RENDER_WATCH_SECRET>`. It sends one Telegram notice after each deploy reaches a final status (`live`, failed, or canceled), and stores notice IDs in PostgreSQL to avoid repeats. This uses Render API credentials kept in Render Environment; no GitHub Actions workflow or GitHub Secrets are used.

Add `RENDER_API_KEY` and a long random `RENDER_WATCH_SECRET` in Render → Environment. Render automatically provides `RENDER_SERVICE_ID`. Keep `BOT_TOKEN` and numeric `ADMIN_USER_ID` set there, and send `/start` to the bot as Admin. Configure a separate HTTP monitor (for example, UptimeRobot) to request `https://YOUR-APP.onrender.com/ops/render-deploy-watch/YOUR_SECRET` every five minutes. Treat the monitor URL as a secret. The endpoint returns a pending status while a deploy is in progress and checks again at the next monitor request.

This is polling, so notices can be delayed up to the monitor interval. It requires the existing service to be reachable when the monitor calls it; if the service is fully unavailable, it cannot notify through itself. Render's direct workspace webhooks can deliver official deploy events, but require a Pro workspace.

## 4. Everyday use

1. Select the month and KHR or USD at the top.
2. Tap Add expense or Add income, enter the amount, category and date, then Save.
3. Tap any history row to edit it or delete after confirmation.
4. Set a monthly budget for each currency from the Budget tab.
5. Switch Khmer/English using the header button. Export all history from Settings.

Dates use Asia/Phnom_Penh. Future transaction dates are rejected. The API accepts month filters from 2000 through 2100. Transactions may have up to 300 note characters. An app session expires after one hour; close and reopen it to refresh Telegram authentication. Authentication data is never stored in localStorage; only the language preference is.

## Local development

```powershell
.venv\Scripts\python -m flask --app wsgi run --port 5000
```

Linux/macOS: `.venv/bin/python -m flask --app wsgi run --port 5000`.

Use `DATABASE_URL=sqlite:///money.db` locally. For a real Telegram test, expose the local server through an HTTPS development tunnel, update `APP_URL`, and run `setup_bot.py` again. The repository does not include an authentication bypass. No live Telegram token is needed for automated tests.

## Tests

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

Tests cover signed authentication, expired/forged sessions, user ownership, create retry deduplication, edit/delete, money precision, currency/month budget isolation, CSV escaping and webhook secret checks. PostgreSQL and live Telegram deployment require verification with your own service configuration.

## Troubleshooting

- **Access disabled:** send `/id`, set the correct numeric allowlist and redeploy.
- **Session expired:** close and reopen the Mini App from the bot.
- **Menu missing:** run `setup_bot.py`, reopen the private bot chat, send `/start`.
- **Connection timeout:** check hosting health and database availability, then retry. A create retry within the same open form will not create another entry. After closing an uncertain form, check history before entering it again.
- **Bot doesn't answer:** check webhook URL/secret agreement and Render logs. Token must match the bot you opened. Re-run setup after changing the URL.
- **Amounts seem different:** check selected month and currency. Riel and dollars are intentionally not added together.

## Files

- `app.py`: API, database schema, Telegram authentication and webhook.
- `wsgi.py`: web service entry point.
- `setup_bot.py`: one-time Telegram registration.
- `static/`: Mini App HTML, CSS and JavaScript.
- `tests/test_app.py`: backend regression tests.
- `.env.example`, `render.yaml`: configuration templates.

## Official references

- https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
- https://core.telegram.org/bots/api#setchatmenubutton
- https://core.telegram.org/bots/api#setwebhook
- https://render.com/docs/deploy-flask

## ការដំឡើងសង្ខេបជាភាសាខ្មែរ

1. បង្កើត Bot តាម `@BotFather` ហើយរក្សា Token ជាសម្ងាត់។
2. Upload code ទៅ GitHub និងបង្កើត Render Web Service។
3. បង្កើត PostgreSQL រួចបំពេញ `DATABASE_URL`។ កុំប្រើ SQLite លើ hosting ដែលលុបទិន្នន័យពេល redeploy។
4. បំពេញ `BOT_TOKEN`, `APP_URL`, `WEBHOOK_SECRET` និង `ALLOWED_USER_IDS`។
5. ដំឡើង dependencies លើកុំព្យូទ័រ បំពេញ `.env` ហើយ run `setup_bot.py`។
6. បើមិនទាន់ដឹង Telegram ID ផ្ញើ `/id` ទៅ Bot បន្ទាប់ពី setup រួច។ បន្ថែមលេខនោះក្នុង `ALLOWED_USER_IDS` ហើយ redeploy។
7. ផ្ញើ `/start` ហើយចុចបើក MyMoney។ មិនចាំបាច់វាយ Command ដើម្បីកត់ចំណាយទេ។

មិនទាន់ deploy ដោយស្វ័យប្រវត្តិទេ៖ អ្នកត្រូវបំពេញ Token, HTTPS URL និង Database របស់អ្នកជាមុន។

### សារជូនដំណឹង Deploy ទៅ Telegram Admin

Render Deploy API watcher ផ្ញើស្ថានភាព deploy ផ្លូវការទៅ Telegram Admin ដោយប្រើ `RENDER_API_KEY`, `RENDER_WATCH_SECRET`, `BOT_TOKEN` និង `ADMIN_USER_ID` នៅក្នុង Render Environment។ បង្កើត HTTP monitor ឱ្យហៅ `https://YOUR-APP.onrender.com/ops/render-deploy-watch/YOUR_SECRET` រៀងរាល់ 5 នាទី។ កុំដាក់ secret ទាំងនេះក្នុង GitHub។

កំណត់ `RENDER_API_KEY` និង `RENDER_WATCH_SECRET` នៅ Render → Environment រួមជាមួយ `BOT_TOKEN` និង `ADMIN_USER_ID` ដែលអ្នកប្រើរួច។ Render ផ្ដល់ `RENDER_SERVICE_ID` ដោយស្វ័យប្រវត្តិ។ Admin ត្រូវផ្ញើ `/start` ទៅ Bot ម្ដង។ កុំបញ្ចូល secret ណាមួយក្នុង GitHub។

## Admin approval behavior

New users send /start and tap Request access, or send /request. The bot displays their own ID. An admin receives their name/ID and Approve/Reject buttons. Decisions are saved in the new access_requests table; existing transaction/budget tables are not altered. A deployment creates this new table automatically.

Only ADMIN_USER_ID may approve or reject. Callback decisions apply only to pending requests; repeated/stale clicks cannot reverse them. Notifications for the same pending user are throttled to one per minute. If Telegram delivery fails, requests remain saved and the admin can use /requests to retrieve batches of five. Decisions remain saved even if a user blocks the notification; the user can reopen the app to check.

Rejected users cannot automatically reapply. The owner can grant or revoke access through /admin with confirmation. Saved decisions override ALLOWED_USER_IDS. Revoking access preserves records. The owner can review users' transactions, budgets and savings goals through the Telegram admin panel and Mini App. Only the configured owner can edit or add a user's transactions or send direct messages; deleted transactions are archived in the user's Trash for restoration. Admin users cannot use these owner-only actions. Users are informed that the owner/admin can review their financial records.

When upgrading an existing deployment, re-register the webhook with allowed_updates including BOTH message and callback_query. The new setup script/Start Command handles this. A setWebhook success does not by itself prove delivery; inspect getWebhookInfo and service logs if /id does not respond.

## Upgrade and warning behavior

Upload ALL project files, including admin_panel.py and static/index.html, style.css and app.js. Do not replace only app.js. Keep your existing Neon DATABASE_URL. New tables are created automatically; existing financial records are retained.

Telegram budget warnings run when saving an expense or monthly budget, for the current month in Asia/Phnom_Penh. One alert per threshold (80%, 100%), currency and month; changing the budget does not reset sent alerts. There is no background reminder scheduler. Failed notification delivery does not roll back the saved transaction.

Savings totals are manual records, not bank transfers and do not change income/expenses. The owner must set their own numeric ADMIN_USER_ID in Render; no admin identity is hardcoded.

## Personal-use update

- The calculator has been removed at the owner’s request.
- My receipts: tap an expense to open a clean personal record summary, then Edit to edit/delete. These are summaries of your entries, not merchant-issued receipts. Photo attachments are supported; OCR, PDF receipt export and recurring payments are not implemented.
- Owner greeting defaults to Thearith; change ADMIN_DISPLAY_NAME in Render if desired. This changes the Mini App greeting only, not Telegram profile or admin identity. ADMIN_USER_ID is still required.
- Telegram: Close menu button or /closemenu hides the reply keyboard; /menu or /start opens it again. /id does not force it back open. The separate Telegram MyMoney launcher is unchanged.
- Daily allowance: the Home page divides the selected currency's current-month budget remaining by the days left, including today. Telegram `/allowance` shows the same calculation for each currency with a budget. Set a monthly budget first.
- Upload static/personal.js together with all other files.

## New interface and transaction management

Home now focuses on monthly totals, the current summary and recent activity. Insights contains the daily bar chart and category donut, including percentages, exact amounts, largest category and empty-state support. Donut values follow the selected month/currency and update after edits/deletions. Desktop uses two columns at 900px and above; mobile remains one column. Budget editing is available through the Home budget card’s Manage button.

History supports Add expense/income, tap-to-view, Edit and individual Delete. Select enables checkboxes; Select visible selects only currently rendered rows. Load more reveals additional rows. Filtering discards selections outside the current filter. Delete selected previews the count before confirmation.

Manage my data → Delete all my entries covers all of your transaction history, across months and both currencies. It preserves budgets, goals and access settings. The dialog requires typing DELETE. Deletion moves records to Trash. Restore from Settings → Trash; only Delete forever inside Trash is permanent. The server uses an owner-bound, five-minute, single-use snapshot, so later entries are not included. Creating a new preview invalidates the old one. No live user records are deleted during deployment.

Upload the full static folder, including design.js, design.css and history.js. The backend creates the delete_batches table automatically. Keep your existing Neon DATABASE_URL.

## Profile, receipt photos, trash and category budgets

- Settings → My profile: save a display name (1–80 characters) and optional bio (160 characters). Saved per Telegram user in Neon; changes the App greeting, not Telegram identity/admin rights.
- All individual and bulk transaction deletions now move records into Trash. Settings → Trash lists 100 records at a time with Load more. Restore keeps the original amount/date/category and receipt photo; active totals and charts include it again. Delete forever requires confirmation and removes the photo. Trash has no automatic expiration. Budgets/goals retain their existing behavior.
- Open an expense record to attach one receipt photo. JPEG/PNG/WebP, maximum input 2 MB / 20 megapixels; animated images are rejected. Server normalizes to JPEG, removes metadata and resizes to at most 1600×1600. Photos are stored as database bytes in Neon, not ephemeral Render disk. They consume database storage. Only the signed-in owner can fetch/upload/remove through the photo API. Upload after saving the expense.
- Home → monthly budget → Manage also contains Category budgets. Limits are keyed by user/month/currency/category; set again to edit, Remove limit to delete. Progress and 80%/100% warnings are in-app. Existing Telegram alerts still concern the overall monthly budget.
- Insights → Month comparison shows expense totals for the selected and previous calendar months, difference and percent change. Current-month comparisons are marked incomplete; a zero previous-month baseline shows no percentage.
- Added subtle card, modal, chart and button animations. Device Reduce Motion disables animations.
- Update all files, including personal_features.py and static/features.js, and reinstall requirements (Pillow is new). New tables are additive; no existing financial records are deleted by deployment.

## Hide amounts and favorites

The eye button in the header hides monetary values in the current browser until toggled back on; the choice is stored locally in that browser. It is a quick privacy aid for shoulder viewing, not a password lock. Up to 12 personal favorites can be saved from an entry form and launched from Home. A favorite fills a draft; review it and press Save to make a transaction. Removing a favorite does not delete transactions.
