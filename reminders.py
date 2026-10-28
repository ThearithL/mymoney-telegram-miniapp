"""Personal reminders for MyMoney.

A reminder is a short note with a date (and an optional time) that the user wants to be
reminded about. It can be general, or linked to a bill, a debt or a savings goal.
Nothing is posted automatically: reminders never create transactions.

Dates travel as ``yyyy-mm-dd`` and times as ``HH:MM``. The client always shows dates as
``dd/mm/yyyy``. The server validates real calendar dates (``2026-02-31`` is rejected).

Status words (relative to today in Phnom Penh): ``overdue``, ``today``, ``week`` (within
the next 7 days) or ``later``. The list is sorted nearest date first.
"""
import re
import time
from datetime import date, datetime

from flask import abort, g
from sqlalchemy import (BigInteger, Column, Date, Integer, String, Table, delete, insert,
                        select, update)

MAX_ITEMS = 200
MAX_TITLE = 80
MAX_NOTE = 500
WEEK_DAYS = 7
REF_TYPES = ('general', 'bill', 'debt', 'goal')
TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def define_tables(metadata):
    return {
        'reminders': Table('user_reminders', metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', BigInteger, nullable=False, index=True),
            Column('ref_type', String(10), nullable=False, default='general'),
            Column('ref_id', Integer, nullable=True),
            Column('title', String(MAX_TITLE), nullable=False),
            Column('amount', BigInteger, nullable=True),
            Column('currency', String(3), nullable=True),
            Column('note', String(MAX_NOTE), nullable=False, default=''),
            Column('remind_date', Date, nullable=False),
            Column('remind_time', String(5), nullable=True),
            Column('created_at', BigInteger, nullable=False)),
    }


def parse_date(value):
    """Strict ``yyyy-mm-dd`` -> date, or None when it is not a real calendar date."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if 2000 <= parsed.year <= 2100 else None


def status_for(remind_date, today):
    days = (remind_date - today).days
    if days < 0:
        return 'overdue'
    if days == 0:
        return 'today'
    return 'week' if days <= WEEK_DAYS else 'later'


def sort_key(row):
    """Nearest date first; within a day, timed reminders by time, untimed last."""
    return (row['remind_date'], row['remind_time'] or '99:99', row['id'])


def summarize(rows, today):
    counts = {'overdue': 0, 'today': 0, 'week': 0, 'later': 0}
    for row in rows:
        counts[status_for(row['remind_date'], today)] += 1
    # "This week" in the summary means today through the next 7 days, today included.
    return {'overdue': counts['overdue'], 'today': counts['today'],
            'week': counts['today'] + counts['week'], 'total': len(rows)}


def register_reminders(app, engine, tables, goals, auth, json_body, amount_units, tz):
    table = tables['reminders']
    bills = tables['recurring_items']
    debts = tables['debts']

    def today():
        return datetime.now(tz).date()

    def linked_ok(conn, ref_type, ref_id):
        source = {'bill': bills, 'debt': debts, 'goal': goals}[ref_type]
        return conn.execute(select(source.c.id).where(
            source.c.id == ref_id, source.c.user_id == g.user['id'])).first() is not None

    def fields(body):
        ref_type = body.get('ref_type', 'general')
        ref_id = body.get('ref_id')
        title = body.get('title')
        note = body.get('note', '')
        raw_amount = body.get('amount')
        remind_date = parse_date(body.get('remind_date'))
        remind_time = body.get('remind_time')
        if ref_type not in REF_TYPES:
            abort(400, 'Choose a valid reminder type.')
        if ref_type == 'general':
            ref_id = None
        elif type(ref_id) is not int or ref_id <= 0:
            abort(400, 'Choose the record this reminder is about.')
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > MAX_TITLE:
            abort(400, f'Enter a title up to {MAX_TITLE} characters.')
        if note is None:
            note = ''
        if not isinstance(note, str) or len(note) > MAX_NOTE:
            abort(400, f'Note can be up to {MAX_NOTE} characters.')
        if remind_date is None:
            abort(400, 'Enter a valid date.')
        if remind_time in (None, ''):
            remind_time = None
        elif not isinstance(remind_time, str) or not TIME_RE.match(remind_time):
            abort(400, 'Enter a valid time (HH:MM).')
        amount = currency = None
        if raw_amount not in (None, ''):
            currency = body.get('currency')
            amount = amount_units(raw_amount, currency)
        return {'ref_type': ref_type, 'ref_id': ref_id, 'title': title.strip(), 'note': note.strip(),
                'amount': amount, 'currency': currency, 'remind_date': remind_date,
                'remind_time': remind_time}

    def serialize(row, now):
        return {'id': row['id'], 'ref_type': row['ref_type'], 'ref_id': row['ref_id'],
                'title': row['title'], 'amount': row['amount'], 'currency': row['currency'],
                'note': row['note'], 'remind_date': row['remind_date'].isoformat(),
                'remind_time': row['remind_time'],
                'days_until': (row['remind_date'] - now).days,
                'status': status_for(row['remind_date'], now)}

    def owned(conn, identity):
        row = conn.execute(select(table).where(table.c.id == identity,
                                               table.c.user_id == g.user['id'])).mappings().first()
        if not row:
            abort(404, 'Reminder not found.')
        return row

    @app.get('/api/reminders')
    @auth
    def reminders_list():
        now = today()
        with engine.connect() as conn:
            rows = conn.execute(select(table).where(table.c.user_id == g.user['id'])).mappings().all()
        rows = sorted(rows, key=sort_key)
        return {'items': [serialize(r, now) for r in rows], 'summary': summarize(rows, now),
                'today': now.isoformat()}

    @app.post('/api/reminders')
    @auth
    def reminders_add():
        values = fields(json_body())
        with engine.begin() as conn:
            if len(conn.execute(select(table.c.id).where(table.c.user_id == g.user['id'])).all()) >= MAX_ITEMS:
                abort(400, f'You can keep up to {MAX_ITEMS} reminders.')
            if values['ref_type'] != 'general' and not linked_ok(conn, values['ref_type'], values['ref_id']):
                abort(404, 'The linked record was not found.')
            identity = conn.execute(insert(table).values(
                **values, user_id=g.user['id'], created_at=int(time.time()))).inserted_primary_key[0]
        return {'id': identity, 'remind_date': values['remind_date'].isoformat()}, 201

    @app.put('/api/reminders/<int:identity>')
    @auth
    def reminders_update(identity):
        values = fields(json_body())
        with engine.begin() as conn:
            owned(conn, identity)
            if values['ref_type'] != 'general' and not linked_ok(conn, values['ref_type'], values['ref_id']):
                abort(404, 'The linked record was not found.')
            conn.execute(update(table).where(table.c.id == identity,
                                             table.c.user_id == g.user['id']).values(**values))
        return {'ok': True, 'remind_date': values['remind_date'].isoformat()}

    @app.delete('/api/reminders/<int:identity>')
    @auth
    def reminders_delete(identity):
        with engine.begin() as conn:
            owned(conn, identity)
            conn.execute(delete(table).where(table.c.id == identity, table.c.user_id == g.user['id']))
        return {'ok': True}

    return table


def feed_items(rows, today):
    """Bell-feed entries for reminders that are overdue or due today."""
    items = []
    for row in rows:
        status = status_for(row['remind_date'], today)
        if status not in ('overdue', 'today'):
            continue
        items.append({'id': f"reminder:{row['id']}:{row['remind_date'].isoformat()}", 'type': 'reminder',
                      'level': 'danger' if status == 'overdue' else 'warn',
                      'data': {'reminder_id': row['id'], 'title': row['title'], 'note': row['note'],
                               'amount': row['amount'], 'currency': row['currency'],
                               'remind_date': row['remind_date'].isoformat(),
                               'remind_time': row['remind_time'],
                               'days_until': (row['remind_date'] - today).days}})
    return items
