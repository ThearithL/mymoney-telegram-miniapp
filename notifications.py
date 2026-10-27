"""Telegram reminders for MyMoney.

Reminders, all configurable per user from Settings -> Notifications:

* daily  - "log today's spending" nudge at a chosen hour (off by default).
           It is skipped when the user already saved a transaction that day.
* debt   - heads-up when a debt/loan is due soon, due today, or recently overdue
           (on by default; only debts that have a due date are considered).
* bills  - heads-up for recurring bills/subscriptions that are due soon, due today or
           overdue (on by default, see recurring.py).
* weekly - a Sunday-evening summary of the week's income, spending and top category
           (off by default).

The in-app notification center (the bell) is fed by ``/api/notifications/feed``, which
computes budget, debt, savings-goal and bill alerts on demand from the saved data.

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
from insights import budget_snapshot
from recurring import cycle_info, posted_keys

DEFAULTS = {'daily_enabled': 0, 'daily_hour': 20, 'debt_enabled': 1, 'debt_days_before': 1}
# Newer preferences live in their own table so existing databases need no column migration.
EXTRA_DEFAULTS = {'bill_enabled': 1, 'weekly_enabled': 0}
WEEKLY_SEND_HOUR = 19       # Sunday 19:00 local (or until Monday noon if the app was asleep)
BILL_SEND_HOUR = 8          # bill reminders go out from 08:00 local time
NO_LOG_FEED_HOUR = 18       # the in-app feed nudges after 18:00 if nothing was logged
GOAL_LEVELS = (80, 100)
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
        'notification_extra': Table('notification_extra', metadata,
            Column('user_id', BigInteger, primary_key=True),
            Column('bill_enabled', Integer, nullable=False, default=1),
            Column('weekly_enabled', Integer, nullable=False, default=0)),
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


def when_text(days_until):
    if days_until == 0:
        return 'ដល់កំណត់ថ្ងៃនេះ / due today'
    if days_until > 0:
        return (f"ដល់កំណត់ក្នុង {days_until} ថ្ងៃ / due in {days_until} "
                f"{_plural(days_until, 'day', 'days')}")
    late = -days_until
    return f"ហួសកំណត់ {late} ថ្ងៃ / {late} {_plural(late, 'day', 'days')} overdue"


def bill_line(item, days_until):
    icon = '💵' if item['kind'] == 'income' else '🧾'
    return f"• {icon} {item['title']}: {money(item['amount'], item['currency'])} · {when_text(days_until)}"


def weekly_text(start, totals, top, previous):
    """Build the Sunday summary. ``totals`` is {(currency, kind): (sum, count)}."""
    lines = [f"📅 សង្ខេបប្រចាំសប្តាហ៍ / Weekly summary\n{start.isoformat()} → {(start + timedelta(days=6)).isoformat()}"]
    for currency in ('KHR', 'USD'):
        spent = totals.get((currency, 'expense'), (0, 0))[0]
        income = totals.get((currency, 'income'), (0, 0))[0]
        if not spent and not income:
            continue
        line = (f"{currency}: ចំណូល / income {money(income, currency)} · "
                f"ចំណាយ / spent {money(spent, currency)}")
        before = previous.get(currency, 0)
        if before and spent:
            change = round((spent - before) * 100 / before)
            line += f" ({'+' if change >= 0 else ''}{change}% vs last week)"
        lines.append(line)
        if top.get(currency):
            lines.append(f"   🏷 {top[currency][0]}: {money(top[currency][1], currency)}")
    return '\n'.join(lines)


def register_notifications(app, engine, tables, transactions, debts, debt_payments, auth,
                           json_body, telegram, has_access, tz, budgets=None, goals=None):
    settings = tables['notification_settings']
    extra = tables['notification_extra']
    log = tables['notification_log']
    recurring = tables['recurring_items']
    last_test = {}

    # ---- helpers -------------------------------------------------------------------
    def load_settings(conn, uid):
        row = conn.execute(select(settings).where(settings.c.user_id == uid)).mappings().first()
        more = conn.execute(select(extra).where(extra.c.user_id == uid)).mappings().first()
        out = {key: (row[key] if row else default) for key, default in DEFAULTS.items()}
        out.update({key: (more[key] if more else default) for key, default in EXTRA_DEFAULTS.items()})
        return out

    def public(values):
        return {'daily_enabled': bool(values['daily_enabled']), 'daily_hour': int(values['daily_hour']),
                'debt_enabled': bool(values['debt_enabled']), 'debt_days_before': int(values['debt_days_before']),
                'bill_enabled': bool(values['bill_enabled']), 'weekly_enabled': bool(values['weekly_enabled'])}

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

    def parse_extra(body, current):
        """bill_enabled / weekly_enabled are optional so older clients keep working."""
        out = {}
        for key in EXTRA_DEFAULTS:
            if key in body:
                if type(body[key]) is not bool:
                    abort(400, 'Turn each reminder on or off.')
                out[key] = int(body[key])
            else:
                out[key] = int(current[key])
        return out

    def upsert(table, uid, values):
        for _ in range(2):
            try:
                with engine.begin() as conn:
                    if conn.execute(update(table).where(table.c.user_id == uid).values(**values)).rowcount == 0:
                        conn.execute(insert(table).values(user_id=uid, **values))
                return
            except IntegrityError:  # two saves raced to create the row; retry as an update
                continue

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

    def run_bills(now, stats):
        if now.hour < BILL_SEND_HOUR:
            return
        today = now.date()
        with engine.connect() as conn:
            rows = conn.execute(select(recurring).where(recurring.c.active == 1)).mappings().all()
        by_user = {}
        for row in rows:
            by_user.setdefault(row['user_id'], []).append(row)
        for uid, items in by_user.items():
            with engine.connect() as conn:
                prefs = load_settings(conn, uid)
                done = posted_keys(conn, transactions, uid, today, [r['id'] for r in items])
            if not prefs['bill_enabled']:
                continue
            if not has_access(uid):
                stats['skipped'] += 1
                continue
            claimed, lines = [], []
            for item in items:
                info = cycle_info(item, today, item['id'] in done)
                days = info['days_until']
                if info['status'] == 'paid':
                    continue
                if info['status'] == 'overdue':
                    if -days > OVERDUE_DAYS:
                        continue
                elif days > item['remind_days']:
                    continue
                stage = 'overdue' if days < 0 else 'today' if days == 0 else 'soon'
                ref = f"{item['id']}:{stage}:{info['due_date']}"
                if claim(uid, 'bill', ref):
                    claimed.append(ref)
                    lines.append(bill_line(item, days))
            if not claimed:
                continue
            text = '🧾 ការរំលឹកវិក្កយបត្រ / Bill reminder\n' + '\n'.join(lines)
            if send(uid, text):
                stats['bill'] += len(claimed)
            else:
                for ref in claimed:
                    release(uid, 'bill', ref)
                stats['failed'] += 1

    def week_totals(conn, uid, start):
        end = start + timedelta(days=7)
        rows = conn.execute(select(transactions.c.currency, transactions.c.kind,
            func.sum(transactions.c.amount), func.count()).where(
            transactions.c.user_id == uid, transactions.c.day >= start,
            transactions.c.day < end).group_by(transactions.c.currency, transactions.c.kind)).all()
        return {(c, k): (int(total), int(n)) for c, k, total, n in rows}

    def run_weekly(now, stats):
        if now.weekday() == 6 and now.hour >= WEEKLY_SEND_HOUR:
            start = now.date() - timedelta(days=6)
        elif now.weekday() == 0 and now.hour < 12:
            start = now.date() - timedelta(days=7)
        else:
            return
        with engine.connect() as conn:
            candidates = conn.execute(select(extra.c.user_id).where(extra.c.weekly_enabled == 1)).scalars().all()
        for uid in candidates:
            if not has_access(uid):
                stats['skipped'] += 1
                continue
            ref = start.isoformat()
            with engine.connect() as conn:
                totals = week_totals(conn, uid, start)
                if not totals:
                    continue
                before = {c: v[0] for (c, k), v in week_totals(conn, uid, start - timedelta(days=7)).items()
                          if k == 'expense'}
                top = {}
                for currency, category, total in conn.execute(select(
                        transactions.c.currency, transactions.c.category, func.sum(transactions.c.amount)).where(
                        transactions.c.user_id == uid, transactions.c.kind == 'expense',
                        transactions.c.day >= start, transactions.c.day < start + timedelta(days=7)
                        ).group_by(transactions.c.currency, transactions.c.category)).all():
                    if currency not in top or total > top[currency][1]:
                        top[currency] = (category, int(total))
            if not claim(uid, 'weekly', ref):
                continue
            if send(uid, weekly_text(start, totals, top, before)):
                stats['weekly'] += 1
            else:
                release(uid, 'weekly', ref)
                stats['failed'] += 1

    def run_reminders(now=None):
        if now is None:
            now = datetime.now(tz)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        else:
            now = now.astimezone(tz)
        stats = {'daily': 0, 'debt': 0, 'bill': 0, 'weekly': 0, 'skipped': 0, 'failed': 0}
        run_daily(now, stats)
        run_debts(now, stats)
        run_bills(now, stats)
        run_weekly(now, stats)
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
        body = json_body()
        values = parse(body)
        uid = g.user['id']
        with engine.connect() as conn:
            current = load_settings(conn, uid)
        more = parse_extra(body, current)
        upsert(settings, uid, values)
        upsert(extra, uid, more)
        return public({**values, **more})

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

    @app.get('/api/notifications/feed')
    @auth
    def notifications_feed():
        """Alerts for the in-app bell. Computed on demand; nothing is stored.

        Each item has a stable ``id`` (it changes when the situation changes, e.g. a
        new budget level), so the app can remember which ones were already read.
        """
        uid = g.user['id']
        now = datetime.now(tz)
        today = now.date()
        month = today.strftime('%Y-%m')
        items = []
        with engine.connect() as conn:
            prefs = load_settings(conn, uid)
            debt_rows = conn.execute(select(debts).where(
                debts.c.user_id == uid, debts.c.status == 'open', debts.c.due_date.is_not(None),
                debts.c.due_date <= today + timedelta(days=DEBT_LOOKAHEAD_DAYS),
                debts.c.due_date >= today - timedelta(days=OVERDUE_DAYS))).mappings().all()
            paid = {}
            if debt_rows:
                paid = dict(conn.execute(select(debt_payments.c.debt_id, func.sum(debt_payments.c.amount)).where(
                    debt_payments.c.debt_id.in_([r['id'] for r in debt_rows])).group_by(debt_payments.c.debt_id)).all())
            bill_rows = conn.execute(select(recurring).where(
                recurring.c.user_id == uid, recurring.c.active == 1)).mappings().all()
            done = posted_keys(conn, transactions, uid, today, [r['id'] for r in bill_rows])
            logged_today = conn.execute(select(func.count()).select_from(transactions).where(
                transactions.c.user_id == uid, transactions.c.day == today)).scalar()
            goal_rows = []
            if goals is not None:
                goal_rows = conn.execute(select(goals).where(
                    goals.c.user_id == uid, goals.c.archived == 0)).mappings().all()

        if budgets is not None:
            snap = budget_snapshot(engine, transactions, budgets, uid, month, today)
            for cur in snap['currencies']:
                if cur['status'] in ('warning', 'reached', 'over'):
                    items.append({'id': f"budget:{month}:{cur['currency']}:{cur['status']}", 'type': 'budget',
                                  'level': 'warn' if cur['status'] == 'warning' else 'danger',
                                  'data': {'currency': cur['currency'], 'status': cur['status'],
                                           'percent': cur['used_percent'], 'spent': cur['expense'],
                                           'budget': cur['budget'], 'remaining': cur['remaining'],
                                           'overspent': cur['overspent']}})

        for debt in debt_rows:
            days = (debt['due_date'] - today).days
            stage = debt_stage(days, prefs['debt_days_before'] if prefs['debt_enabled'] else DEBT_LOOKAHEAD_DAYS)
            remaining = debt['amount'] - int(paid.get(debt['id'], 0) or 0)
            if not stage or remaining <= 0:
                continue
            items.append({'id': f"debt:{debt['id']}:{stage}:{debt['due_date'].isoformat()}", 'type': 'debt',
                          'level': 'warn' if stage == 'soon' else 'danger',
                          'data': {'person': debt['person'], 'direction': debt['direction'],
                                   'remaining': remaining, 'currency': debt['currency'],
                                   'days_until': days, 'due_date': debt['due_date'].isoformat()}})

        for item in bill_rows:
            info = cycle_info(item, today, item['id'] in done)
            days = info['days_until']
            if info['status'] == 'paid' or days > max(item['remind_days'], 3):
                continue
            if info['status'] == 'overdue' and -days > OVERDUE_DAYS:
                continue
            items.append({'id': f"bill:{item['id']}:{info['due_date']}", 'type': 'bill',
                          'level': 'danger' if days < 0 else 'warn',
                          'data': {'recurring_id': item['id'], 'title': item['title'], 'kind': item['kind'],
                                   'amount': item['amount'], 'currency': item['currency'],
                                   'days_until': days, 'due_date': info['due_date']}})

        for goal in goal_rows:
            if goal['target'] <= 0:
                continue
            percent = int(goal['saved'] * 100 // goal['target'])
            level = max([lv for lv in GOAL_LEVELS if percent >= lv], default=0)
            if level:
                items.append({'id': f"goal:{goal['id']}:{level}", 'type': 'goal', 'level': 'info',
                              'data': {'title': goal['title'], 'level': level, 'currency': goal['currency'],
                                       'saved': goal['saved'], 'target': goal['target']}})

        if now.hour >= NO_LOG_FEED_HOUR and not logged_today:
            items.append({'id': f'nolog:{today.isoformat()}', 'type': 'nolog', 'level': 'info', 'data': {}})

        rank = {'danger': 0, 'warn': 1, 'info': 2}
        items.sort(key=lambda i: (rank[i['level']], i['id']))
        return {'items': items, 'today': today.isoformat()}

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
