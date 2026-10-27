"""Recurring bills, subscriptions and regular income for MyMoney.

A recurring item is a template (title, amount, category, day of the month). It never
creates data by itself: the user taps "Mark paid" (or "Mark received") and a normal
transaction is saved for today. The transaction's request_id is derived from the item
and the month, so one item can be recorded at most once per month, even on retries.

Reminders for due items are sent by ``notifications.run_reminders`` and the in-app
notification center also lists them.
"""
import calendar
import time
from datetime import date, datetime

from flask import abort, g, request
from sqlalchemy import (BigInteger, Column, Integer, String, Table, delete, insert,
                        select, update)
from sqlalchemy.exc import IntegrityError

MAX_ITEMS = 60
MAX_REMIND_DAYS = 7
SOON_DAYS = 3


def define_tables(metadata):
    return {
        'recurring_items': Table('recurring_items', metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', BigInteger, nullable=False, index=True),
            Column('title', String(60), nullable=False),
            Column('kind', String(10), nullable=False),
            Column('amount', BigInteger, nullable=False),
            Column('currency', String(3), nullable=False),
            Column('category', String(20), nullable=False),
            Column('account', String(20), nullable=False),
            Column('day_of_month', Integer, nullable=False),
            Column('remind_days', Integer, nullable=False, default=1),
            Column('active', Integer, nullable=False, default=1),
            Column('created_on', String(10), nullable=False)),
    }


def clamp_day(year, month, day):
    """The due date in a month; day 31 becomes the last day of shorter months."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def next_month(year, month):
    return (year + (month == 12), month % 12 + 1)


def request_key(item_id, year, month):
    return f'rec-{item_id}-{year:04d}-{month:02d}'


def cycle_info(item, today, posted_this_month):
    """Work out the item's next due date and a status word.

    status: 'paid' (recorded this month), 'overdue', 'today', 'soon' or 'upcoming'.
    An item created after this month's due date waits for next month instead of
    showing as overdue straight away.
    """
    day = int(item['day_of_month'])
    due = clamp_day(today.year, today.month, day)
    created = date.fromisoformat(item['created_on'])
    if posted_this_month or due < created:
        year, month = next_month(today.year, today.month)
        due = clamp_day(year, month, day)
        status = 'paid' if posted_this_month else None
    else:
        status = None
    days_until = (due - today).days
    if status is None:
        if days_until < 0:
            status = 'overdue'
        elif days_until == 0:
            status = 'today'
        elif days_until <= max(SOON_DAYS, int(item['remind_days'])):
            status = 'soon'
        else:
            status = 'upcoming'
    return {'due_date': due.isoformat(), 'days_until': days_until, 'status': status,
            'posted_this_month': bool(posted_this_month)}


def posted_keys(conn, transactions, uid, today, item_ids):
    """Set of item ids already recorded in today's month."""
    if not item_ids:
        return set()
    keys = {request_key(i, today.year, today.month): i for i in item_ids}
    rows = conn.execute(select(transactions.c.request_id).where(
        transactions.c.user_id == uid, transactions.c.request_id.in_(list(keys)))).scalars().all()
    return {keys[k] for k in rows}


def register_recurring(app, engine, tables, transactions, auth, json_body, amount_units,
                       categories, custom_categories, tz, budget_warning=None):
    items = tables['recurring_items']

    def today():
        return datetime.now(tz).date()

    def category_ok(key, kind):
        if not isinstance(key, str):
            return False
        if key in categories:
            if key == 'salary':
                return kind == 'income'
            if key == 'other':
                return True
            return kind == 'expense'
        with engine.connect() as conn:
            found = conn.execute(select(custom_categories.c.kind).where(
                custom_categories.c.user_id == g.user['id'],
                custom_categories.c.key == key)).scalar_one_or_none()
        return found is not None and found in (kind, 'both')

    def fields(body):
        title = body.get('title')
        kind = body.get('kind', 'expense')
        currency = body.get('currency')
        category = body.get('category')
        account = body.get('account', 'cash')
        day = body.get('day_of_month')
        remind = body.get('remind_days', 1)
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 60:
            abort(400, 'Enter a name up to 60 characters.')
        if kind not in ('expense', 'income'):
            abort(400, 'Choose expense or income.')
        if account not in ('cash', 'bank'):
            abort(400, 'Choose cash or bank.')
        if type(day) is not int or not 1 <= day <= 31:
            abort(400, 'Day of month must be 1 to 31.')
        if type(remind) is not int or not 0 <= remind <= MAX_REMIND_DAYS:
            abort(400, f'Reminder must be 0 to {MAX_REMIND_DAYS} days before.')
        if not category_ok(category, kind):
            abort(400, 'Choose a valid category.')
        return {'title': title.strip(), 'kind': kind, 'amount': amount_units(body.get('amount'), currency),
                'currency': currency, 'category': category, 'account': account,
                'day_of_month': day, 'remind_days': remind}

    def serialize(row, info):
        return {'id': row['id'], 'title': row['title'], 'kind': row['kind'], 'amount': row['amount'],
                'currency': row['currency'], 'category': row['category'], 'account': row['account'],
                'day_of_month': row['day_of_month'], 'remind_days': row['remind_days'],
                'active': bool(row['active']), **info}

    def owned(conn, identity):
        row = conn.execute(select(items).where(items.c.id == identity,
                                               items.c.user_id == g.user['id'])).mappings().first()
        if not row:
            abort(404, 'Recurring item not found.')
        return row

    @app.get('/api/recurring')
    @auth
    def recurring_list():
        now = today()
        with engine.connect() as conn:
            rows = conn.execute(select(items).where(items.c.user_id == g.user['id'])
                                .order_by(items.c.day_of_month.asc(), items.c.id.asc())).mappings().all()
            done = posted_keys(conn, transactions, g.user['id'], now, [r['id'] for r in rows])
        result = []
        for row in rows:
            info = cycle_info(row, now, row['id'] in done)
            if not row['active']:
                info['status'] = 'paused'
            result.append(serialize(row, info))
        order = {'overdue': 0, 'today': 1, 'soon': 2, 'upcoming': 3, 'paid': 4, 'paused': 5}
        result.sort(key=lambda r: (order[r['status']], r['due_date'], r['id']))
        totals = {}
        for r in result:
            if r['kind'] == 'expense' and r['active']:
                totals[r['currency']] = totals.get(r['currency'], 0) + r['amount']
        return {'items': result, 'monthly_expense_totals': totals, 'today': now.isoformat()}

    @app.post('/api/recurring')
    @auth
    def recurring_add():
        values = fields(json_body())
        with engine.begin() as conn:
            count = conn.execute(select(items.c.id).where(items.c.user_id == g.user['id'])).all()
            if len(count) >= MAX_ITEMS:
                abort(400, f'You can keep up to {MAX_ITEMS} recurring items.')
            identity = conn.execute(insert(items).values(
                **values, user_id=g.user['id'], active=1,
                created_on=today().isoformat())).inserted_primary_key[0]
        return {'id': identity}, 201

    @app.put('/api/recurring/<int:identity>')
    @auth
    def recurring_update(identity):
        body = json_body()
        values = fields(body)
        if 'active' in body:
            if type(body['active']) is not bool:
                abort(400, 'Active must be true or false.')
            values['active'] = int(body['active'])
        with engine.begin() as conn:
            owned(conn, identity)
            conn.execute(update(items).where(items.c.id == identity,
                                             items.c.user_id == g.user['id']).values(**values))
        return {'ok': True}

    @app.post('/api/recurring/<int:identity>/active')
    @auth
    def recurring_toggle(identity):
        body = json_body()
        if type(body.get('active')) is not bool:
            abort(400, 'Active must be true or false.')
        with engine.begin() as conn:
            owned(conn, identity)
            conn.execute(update(items).where(items.c.id == identity,
                                             items.c.user_id == g.user['id']).values(active=int(body['active'])))
        return {'ok': True}

    @app.delete('/api/recurring/<int:identity>')
    @auth
    def recurring_delete(identity):
        with engine.begin() as conn:
            owned(conn, identity)
            conn.execute(delete(items).where(items.c.id == identity, items.c.user_id == g.user['id']))
        return {'ok': True}

    @app.post('/api/recurring/<int:identity>/post')
    @auth
    def recurring_post(identity):
        """Record this month's payment/receipt as a normal transaction dated today."""
        now = today()
        with engine.connect() as conn:
            row = owned(conn, identity)
        if not row['active']:
            abort(409, 'This item is paused. Resume it first.')
        key = request_key(identity, now.year, now.month)
        values = {'kind': row['kind'], 'amount': row['amount'], 'currency': row['currency'],
                  'category': row['category'], 'account': row['account'], 'note': row['title'][:300],
                  'day': now, 'user_id': g.user['id'], 'request_id': key}
        try:
            with engine.begin() as conn:
                tx_id = conn.execute(insert(transactions).values(**values)).inserted_primary_key[0]
        except IntegrityError:
            abort(409, 'Already recorded this month.')
        if row['kind'] == 'expense' and budget_warning:
            try:
                budget_warning(g.user['id'], now.strftime('%Y-%m'), row['currency'])
            except Exception:  # a failed Telegram warning must not undo the saved entry
                app.logger.exception('Budget warning failed after recurring post')
        return {'ok': True, 'transaction_id': tx_id}, 201

    return items
