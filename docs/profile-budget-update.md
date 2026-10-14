# Profile and budget overview update — 2026-10-14

The bot admin panel previously displayed Telegram's first name even when the app used a saved profile name. The configured admin account 1219084924 is now renamed to Thearith once during startup. Later profile edits persist across messages and restarts; balances, budgets, biography and permissions are preserved.

New commands: `/profile`, `/name Your Name`, `/budgetstatus`, and `/insights`. The app Budget tab links to the new overview, with month selection, separate USD/KHR totals, remaining or overspent budget, usage percentages, daily allowance and the previous full month's expenses. The overview can also update the user's own display name. Existing frontend and exchange-rate behavior remain available.

The two new authenticated APIs use signed Telegram initData and the existing access checks. Daily allowance rounds down to cents/riel and counts today among remaining days. Missing and zero budgets have separate behavior. In-progress month comparisons are labelled.

Validation: all 10 focused profile/budget tests pass. The repository-wide run reports 87 passed and 10 failed; these same 10 failures reproduce on unchanged application code (existing test fixture/session issues and debt-name validation). The unchanged baseline snapshot also lacked static assets, causing one additional unrelated static-file failure. Actual Telegram WebView and live database behavior require deployment checks.

Render already runs `setup_bot.py` in its startup script, so new slash commands register automatically. Send `/menu` to refresh the reply keyboard and reopen the Mini App to see the saved name. Existing chat messages are not edited.
