# MyMoney: Vercel Hobby + Neon Free

Prepared for deployment; this archive is not itself a deployed application.

## Account access

Connect Vercel and Neon to ChatGPT before asking the assistant to finish setup.
Use only the free personal Hobby plan and Neon Free. Do not enable paid add-ons.
No real bot token, password, database credentials or financial records are included.

## Deployment

1. Inspect the existing database before creating a replacement. For a migration,
   preserve the current DATABASE_URL when possible. If moving to a new Neon
   database, back up and restore the existing PostgreSQL database, then verify
   row counts and totals for each currency before changing the bot webhook.
2. Create/select a Neon Free project and obtain its pooled PostgreSQL connection
   string with TLS (`sslmode=require`). Store it privately as DATABASE_URL.
3. Import the project into Vercel under a personal Hobby account. Select Flask.
   `pyproject.toml` selects Python 3.12 and exports `wsgi:app`.
   The build command is `python scripts/vercel_build.py`.
   Leave Output Directory at the framework default. Do not use Render's Gunicorn
   start command and do not run setup_bot.py during builds.
4. Set all variables listed in `.env.vercel.example`. Use a stable production
   HTTPS origin for APP_URL. Generate independent WEBHOOK_SECRET and
   FLASK_SECRET_KEY values. Set the actual owner's Telegram ID and admin password
   hash. Keep preview credentials isolated from the production bot/database.
5. Deploy and verify `/health`, `/`, `/insights`, `/static/app.js`, and
   `/insights-assets/app.js`. `/api/data` without Telegram authentication must
   return 401, and `/telegram/webhook` without its secret must return 403.
6. With production variables loaded privately, run `python setup_bot.py` once,
   only after verification. This switches the existing bot's webhook and menu
   to the new URL. It does not send a message to users or discard pending updates.
   Check Telegram getWebhookInfo for the correct URL and absence of delivery errors.
7. Open the actual Telegram bot as the owner. Verify signed Telegram login,
   separate USD/KHR budgets, a test transaction, charts, admin access and deletion
   of the test record. BotFather's Main Mini App URL may also need updating if
   previously configured separately from the bot menu.

## Privacy

The UI shell and Telegram webhook must be reachable for Telegram to load the app
and deliver updates. Financial API data stays behind signed Telegram initData,
owner/allowlist checks and per-user database filtering. A private repository by
itself does not protect a deployed URL. Do not turn off deployment protection
without confirming the intended production access model; protected previews can
be tested before switching Telegram to production.

## Runtime changes

- `scripts/vercel_build.py` copies existing CSS/JS to `public/static` and
  `public/insights-assets` without publishing configuration or data files.
- HTML remains served by Flask; existing asset URLs and security headers are kept.
- Startup rejects missing Vercel credentials and a local SQLite database.
- PostgreSQL uses NullPool on Vercel so each function releases idle connections;
  use Neon's pooled endpoint to manage database connections.
- Existing schema setup runs when the Flask app starts. Bootstrap a fresh
  database before opening traffic. Existing additive migrations remain intact.
- `setup_bot.py` remains an explicit post-deployment step, preventing preview
  builds from stealing the live webhook.
- No Render service is stopped or deleted by these files.

## Local verification

Install `requirements-dev.txt`, then run `python -m pytest -q`.
The local suite uses isolated SQLite databases and mocked Telegram/network calls;
it does not establish that live Neon or Vercel deployment has succeeded.

Official references:
- https://vercel.com/docs/frameworks/backend/flask
- https://vercel.com/docs/functions/runtimes/python
- https://vercel.com/docs/plans/hobby
- https://neon.com/pricing
