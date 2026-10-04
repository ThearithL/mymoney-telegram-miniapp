# លុយខ្ញុំ · MyMoney Telegram Mini App — Dashboard, goals and admin update

A complete, self-hosted personal expense tracker: Python/Flask API + Telegram bot webhook + responsive vanilla HTML/CSS/JavaScript. No frontend build step. Start with `RENDER_SETUP_KH.md` for the simplest Render + Neon deployment and owner bootstrap.

## Included

- Telegram persistent menu, quick expense/income buttons and inline Mini App launch.
- Daily expense chart with data table; today/week/month summaries in app and bot.
- Savings goals with manually entered saved totals, progress and edit/delete.
- Light/dark/system themes, quick-entry drafts, loading animations and retry messages.
- Budget alerts at 80% and 100% in app and Telegram.
- Owner /admin dashboard: users, access controls, records, goals, totals and audit history.
- Request access button, admin Approve/Reject buttons, persistent access decisions in Neon.
- `/id` works before approval; `/request` submits access; `/requests` recovers pending requests for the owner.
- `ADMIN_USER_ID` grants the owner access; nobody can claim admin through the UI.
- Fullscreen request with safe-area spacing on supported Telegram clients.
- Khmer/English interface; mobile navigation, light/dark system theme.
- Add income/expenses, category, cash/bank label, date and optional note.
- Edit, confirmed delete, month/currency filters, history search and pagination.
- Monthly income minus expenses, category bars, monthly budgets, in-app budget warnings.
- KHR stored as integer riel; USD stored as integer cents. Totals stay separate.
- CSV export of your own full history, with spreadsheet formula escaping.
- Server-side Telegram initData signature/age verification, user allowlist, per-user data isolation.
- Duplicate create retries reuse a request ID; SQLAlchemy supports SQLite and PostgreSQL.

**Scope:** This version implements the core tracker. Scheduled reminders, OCR, voice recognition, bank integration, account transfers and exchange-rate conversion are not included. The dashboard net figure is selected-month income minus expenses, not a verified bank balance. Cash/bank are labels only. CSV downloads may depend on Telegram client support; try Telegram Desktop if mobile download is blocked.

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
ALLOWED_USER_IDS=
DATABASE_URL=postgresql://user:password@host/database
```

Optional extra pre-approved IDs in ALLOWED_USER_IDS are comma-separated. If both ADMIN_USER_ID and ALLOWED_USER_IDS are empty, Mini App access is disabled until owner bootstrap. Approved users are stored in access_requests, not environment variables. No credentials are included in this project. Never commit `.env`.

## 2. Deploy to Render with PostgreSQL

1. Put the extracted project files in your own GitHub repository (the directory containing `app.py` should be the service root).
2. Create a PostgreSQL database with a provider of your choice. Copy its connection URL. Configure the provider's required TLS options, e.g. `?sslmode=require` when required.
3. Create a Render **Web Service** from that repository.
4. Build command: `pip install -r requirements.txt`
5. Start command: `python setup_bot.py && gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60`
6. Add the environment variables above. Set `APP_URL` to the actual public HTTPS service URL, without a trailing slash. Set `PYTHON_VERSION` to `3.12.14` if using the included blueprint.
7. Health check path: `/health`. Deploy. Tables are created automatically for a new database.

`render.yaml` is also provided for Blueprint deployment; fill its prompted values. The blueprint does not provision a database or choose a service plan. Check the provider's current plan pricing, idle/sleep behavior, storage retention and backup policy before choosing it.

**Do not use SQLite on an ephemeral host filesystem.** Use external PostgreSQL for deployed data. SQLite is only the local default. CSV is an export, not a full database backup (budgets are excluded). Enable database backups and test restoration. Schema changes in later versions need migrations; `create_all` does not migrate existing tables.

## 3. Connect Telegram to the deployed app

The updated Render Start Command runs setup_bot.py automatically. You can skip local setup below when using that command. For first setup, leave ADMIN_USER_ID and ALLOWED_USER_IDS empty, deploy, send /id to the bot, then place your own numeric ID in ADMIN_USER_ID and redeploy. Send /start once as admin so the bot can notify you.

### Optional local setup

On your computer, set `.env` to the same `BOT_TOKEN`, `APP_URL` and `WEBHOOK_SECRET` as the deployed service, then run:

```powershell
.venv\Scripts\python setup_bot.py
```

Linux/macOS: `.venv/bin/python setup_bot.py`.

The script registers the webhook, chat menu button and `/start`, `/menu`, `/id` commands. It replaces any existing webhook for this bot; use a dedicated bot, and do not run a polling bot with the same token.

**If you don't know your Telegram ID:** deploy initially with an empty `ALLOWED_USER_IDS`, run `setup_bot.py`, then send `/id` in your bot's private chat. Copy that numeric ID into Render's `ALLOWED_USER_IDS` environment variable and redeploy. The `/id` command works before access is allowed. For approval management, put your personal ID in ADMIN_USER_ID, not only in ALLOWED_USER_IDS.

Now send `/start` and tap **💰 Open MyMoney** or the chat menu button. Use a private bot chat. The app must be opened through Telegram for authenticated API access. Ordinary browser access shows the layout and an instruction to open Telegram; it does not bypass login.

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

## Admin approval behavior

New users send /start and tap Request access, or send /request. The bot displays their own ID. An admin receives their name/ID and Approve/Reject buttons. Decisions are saved in the new access_requests table; existing transaction/budget tables are not altered. A deployment creates this new table automatically.

Only ADMIN_USER_ID may approve or reject. Callback decisions apply only to pending requests; repeated/stale clicks cannot reverse them. Notifications for the same pending user are throttled to one per minute. If Telegram delivery fails, requests remain saved and the admin can use /requests to retrieve batches of five. Decisions remain saved even if a user blocks the notification; the user can reopen the app to check.

Rejected users cannot automatically reapply. The owner can grant or revoke access through /admin with confirmation. Saved decisions override ALLOWED_USER_IDS. Revoking access preserves records. The owner can review users' transactions, budgets and savings goals through the Telegram admin panel; the Mini App API remains scoped to the signed-in user. Users are informed of owner visibility. Admin financial editing/deletion and bulk broadcasts are not implemented.

When upgrading an existing deployment, re-register the webhook with allowed_updates including BOTH message and callback_query. The new setup script/Start Command handles this. A setWebhook success does not by itself prove delivery; inspect getWebhookInfo and service logs if /id does not respond.

## Upgrade and warning behavior

Upload ALL project files, including admin_panel.py and static/index.html, style.css and app.js. Do not replace only app.js. Keep your existing Neon DATABASE_URL. New tables are created automatically; existing financial records are retained.

Telegram budget warnings run when saving an expense or monthly budget, for the current month in Asia/Phnom_Penh. One alert per threshold (80%, 100%), currency and month; changing the budget does not reset sent alerts. There is no background reminder scheduler. Failed notification delivery does not roll back the saved transaction.

Savings totals are manual records, not bank transfers and do not change income/expenses. The owner must set their own numeric ADMIN_USER_ID in Render; no admin identity is hardcoded.
