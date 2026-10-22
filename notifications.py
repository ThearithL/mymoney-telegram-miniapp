"""Telegram reminders for MyMoney.

Two kinds of reminder, both configurable per user from Settings -> Notifications:

* daily  - "log today's spending" nudge at a chosen hour (off by default).
           It is skipped when the user already saved a transaction that day.
* debt   - heads-up when a debt/loan is due soon, due today, or recently overdue
           (on by default; only debts that have a due date are considered).

Reminders are produced by ``run_reminders()``. It is safe to call as often as you
like: every message is claimed in ``notification_log`` first, so nothing is sent
twice. Call it from an external uptime monitor via
``/ops/reminders/<REMINDER_SECRET>`` and/or from the optional in-process
scheduler (``REMINDER_SCHEDULER=1``, see wsgi.py).
"""
import hmac
import os
import time
from datetime import datetime, timedelta

from flask import abort, g, jsonify, request
from sqlalchemy import (BigInteger, Column, Date, Integer, String, Table,
                        UniqueConstraint, delete, func, insert, select, update)
from sqlalchemy.exc import IntegrityError

from admin_panel import money

DEFAULTS = {'daily_enabled': 0, 'daily_hour': 20, 'debt_enabled': 1, 'debt_days_before': 1}
DAILY_WINDOW_HOURS = 3      # send the daily nudge between hour and hour+2 (local time)
DEBT_SEND_HOUR = 9          # debt reminders go out from 09:00 local time
DEBT_LOOKAHEAD_DAYS = 7     # largest "days before due" a user can choose
OVERDUE_DAYS = 14           # stop nagging about debts overdue for longer than this
LOG_RETENTION_DAYS = 90
TEST_COOLDOWN_SECONDS = 30


def define_tables(metadata):
    return {
        'notification_settings': Table('notification_settings', metadata,
            Column('user_id', BigInteger, primary_key=True),
            Column('daily_enabled', Integer, nullable=False, default=0),
            Column('daily_hour', Integer, nullable=False, default=20),
            Column('debt_enabled', Integer, nullable=False, default=1),
            Column('debt_days_before', Integer, nullable=False, default=1)),
        'notification_log': Table('notification_log', metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', BigInteger, nullable=False, index=True),
            Column('kind', String(20), nullable=False),
            Column('ref', String(80), nullable=False),
            Column('sent_at', BigInteger, nullable=False),
            UniqueConstraint('user_id', 'kind', 'ref')),
    }


def _plural(n, one, many):
    return one if n == 1 else many


def debt_stage(days_until, days_before):
    """Return 'today', 'overdue', 'soon' or None for a debt due in ``days_until`` days."""
    if days_until == 0:
        return 'today'
    if days_until < 0:
        return 'overdue' if -days_until <= OVERDUE_DAYS else None
    if days_until <= days_before:
        return 'soon'
    return None


def debt_line(debt, remaining, days_until):
    if debt['direction'] == 'lent':
        who = f"{debt['person']} ជំពាក់អ្នក / {debt['person']} owes you"
    else:
        who = f"អ្នកជំពាក់ {debt['person']} / You owe {debt['person']}"
    if days_until == 0:
        when = 'ដល់កំណត់ថ្ងៃនេះ / due today'
    elif days_until > 0:
        when = (f"ដល់កំណត់ក្នុង {days_until} ថ្ងៃ / due in {days_until} "
                f"{_plural(days_until, 'day', 'days')}")
    else:
        late = -days_until
        when = (f"ហួសកំណត់ {late} ថ្ងៃ / {late} {_plural(late, 'day', 'days')} overdue")
    return f"• {who}: {money(remaining, debt['currency'])} · {when}"


def register_notifications(app, engine, tables, transactions, debts, debt_payments, auth,
                           json_body, telegram, has_access, tz):
    settings = tables['notification_settings']
    log = tables['notification_log']
    last_test = {}

    # ---- helpers -------------------------------------------------------------------
    def load_settings(conn, uid):
        row = conn.execute(select(settings).where(settings.c.user_id == uid)).mappings().first()
        return {key: (row[key] if row else default) for key, default in DEFAULTS.items()}

    def public(values):
        return {'daily_enabled': bool(values['daily_enabled']), 'daily_hour': int(values['daily_hour']),
                'debt_enabled': bool(values['debt_enabled']), 'debt_days_before': int(values['debt_days_before'])}

    def parse(body):
        out = {}
        for key in ('daily_enabled', 'debt_enabled'):
            if type(body.get(key)) is not bool:
                abort(400, 'Turn each reminder on or off.')
            out[key] = int(body[key])
        for key, low, high in (('daily_hour', 0, 23), ('debt_days_before', 0, DEBT_LOOKAHEAD_DAYS)):
            value = body.get(key)
            if type(value) is not int or not low <= value <= high:
                abort(400, f'{key} must be a whole number from {low} to {high}.')
            out[key] = value
        return out

    def send(uid, text):
        payload = {'chat_id': uid, 'text': text}
        if str(app.config.get('APP_URL', '')).startswith('https://'):
            payload['reply_markup'] = {'inline_keyboard': [[
                {'text': '💰 បើក / Open MyMoney', 'web_app': {'url': app.config['APP_URL']}}]]}
        return telegram('sendMessage', payload)

    def claim(uid, kind, ref):
        try:
            with engine.begin() as conn:
                conn.execute(insert(log).values(user_id=uid, kind=kind, ref=ref, sent_at=int(time.time())))
            return True
        except IntegrityError:
            return False

    def release(uid, kind, ref):
        with engine.begin() as conn:
            conn.execute(delete(log).where(log.c.user_id == uid, log.c.kind == kind, log.c.ref == ref))

    # ---- reminder engine -----------------------------------------------------------
    def run_daily(now, stats):
        today = now.date()
        with engine.connect() as conn:
            candidates = conn.execute(select(settings.c.user_id, settings.c.daily_hour).where(
                settings.c.daily_enabled == 1)).all()
        for uid, hour in candidates:
            if not hour <= now.hour < hour + DAILY_WINDOW_HOURS:
                continue
            if not has_access(uid):
                stats['skipped'] += 1
                continue
            with engine.connect() as conn:
                logged = conn.execute(select(func.count()).select_from(transactions).where(
                    transactions.c.user_id == uid, transactions.c.day == today)).scalar()
            if logged:
                continue
            ref = today.isoformat()
            if not claim(uid, 'daily', ref):
                continue
            text = ('🔔 ការរំលឹក / Reminder\n'
                    'ថ្ងៃនេះអ្នកមិនទាន់បានកត់ត្រាប្រតិបត្តិការទេ។\n'
                    "You haven't logged anything today.")
            if send(uid, text):
                stats['daily'] += 1
            else:
                release(uid, 'daily', ref)
                stats['failed'] += 1

    def run_debts(now, stats):
        if now.hour < DEBT_SEND_HOUR:
            return
        today = now.date()
        with engine.connect() as conn:
            rows = conn.execute(select(debts).where(
                debts.c.status == 'open', debts.c.due_date.is_not(None),
                debts.c.due_date <= today + timedelta(days=DEBT_LOOKAHEAD_DAYS),
                debts.c.due_date >= today - timedelta(days=OVERDUE_DAYS)
            ).order_by(debts.c.due_date.asc(), debts.c.id.asc())).mappings().all()
            paid = {}
            if rows:
                paid = dict(conn.execute(select(debt_payments.c.debt_id, func.sum(debt_payments.c.amount)).where(
                    debt_payments.c.debt_id.in_([row['id'] for row in rows])
                ).group_by(debt_payments.c.debt_id)).all())
        by_user = {}
        for row in rows:
            by_user.setdefault(row['user_id'], []).append(row)
        for uid, items in by_user.items():
            with engine.connect() as conn:
                prefs = load_settings(conn, uid)
            if not prefs['debt_enabled']:
                continue
            if not has_access(uid):
                stats['skipped'] += 1
                continue
            claimed, lines = [], []
            for debt in items:
                days_until = (debt['due_date'] - today).days
                stage = debt_stage(days_until, prefs['debt_days_before'])
                if not stage:
                    continue
                remaining = debt['amount'] - int(paid.get(debt['id'], 0) or 0)
                if remaining <= 0:
                    continue
                # The stage is part of the key so each stage is announced once, and a
                # changed due date counts as a new reminder.
                ref = f"{debt['id']}:{stage}:{debt['due_date'].isoformat()}"
                if claim(uid, 'debt', ref):
                    claimed.append(ref)
                    lines.append(debt_line(debt, remaining, days_until))
            if not claimed:
                continue
            text = '🔔 ការរំលឹកបំណុល / Debt reminder\n' + '\n'.join(lines)
            if send(uid, text):
                stats['debt'] += len(claimed)
            else:
                for ref in claimed:
                    release(uid, 'debt', ref)
                stats['failed'] += 1

    def run_reminders(now=None):
        if now is None:
            now = datetime.now(tz)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        else:
            now = now.astimezone(tz)
        stats = {'daily': 0, 'debt': 0, 'skipped': 0, 'failed': 0}
        run_daily(now, stats)
        run_debts(now, stats)
        with engine.begin() as conn:
            conn.execute(delete(log).where(log.c.sent_at < int(time.time()) - LOG_RETENTION_DAYS * 86400))
        return stats

    app.extensions['run_reminders'] = run_reminders

    # ---- HTTP API ------------------------------------------------------------------
    @app.get('/api/notifications')
    @auth
    def notifications_get():
        with engine.connect() as conn:
            return public(load_settings(conn, g.user['id']))

    @app.put('/api/notifications')
    @auth
    def notifications_put():
        values = parse(json_body())
        uid = g.user['id']
        for _ in range(2):
            try:
                with engine.begin() as conn:
                    if conn.execute(update(settings).where(settings.c.user_id == uid).values(**values)).rowcount == 0:
                        conn.execute(insert(settings).values(user_id=uid, **values))
                break
            except IntegrityError:  # two saves raced to create the row; retry as an update
                continue
        return public(values)

    @app.post('/api/notifications/test')
    @auth
    def notifications_test():
        uid = g.user['id']
        now = time.time()
        if now - last_test.get(uid, 0) < TEST_COOLDOWN_SECONDS:
            abort(429, 'Please wait a few seconds before sending another test.')
        last_test[uid] = now
        delivered = send(uid, '🔔 ការសាកល្បង / Test\nការជូនដំណឹងដំណើរការហើយ។\nNotifications are working.')
        if not delivered:
            return jsonify(ok=False, error='Telegram could not deliver the message. Open the bot chat and send /start first.'), 502
        return {'ok': True}

    @app.get('/ops/reminders/<key>')
    def reminders_run(key):
        """Call from an uptime monitor every 5-15 minutes. Safe to call repeatedly."""
        expected = (os.getenv('REMINDER_SECRET', '') or os.getenv('RENDER_WATCH_SECRET', '')).strip()
        if not expected or not hmac.compare_digest(key.encode(), expected.encode()):
            abort(404)
        if not app.config['BOT_TOKEN']:
            return jsonify(ok=False, error='BOT_TOKEN is not configured'), 503
        return jsonify(ok=True, **run_reminders())

    return run_reminders
