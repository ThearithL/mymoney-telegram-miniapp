import csv
import hashlib
import hmac
import io
import json
import os
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, DecimalException
from functools import wraps
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from flask import Flask, abort, g, jsonify, request, send_from_directory, Response
from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, BigInteger,
                        String, Text, Date, UniqueConstraint, select, insert, update, delete, func, text, inspect)
from sqlalchemy.exc import IntegrityError
from admin_panel import AdminPanel, money as display_money
from personal_features import define_tables, register_features, archive_rows

load_dotenv()
CATEGORIES = ['food', 'coffee', 'transport', 'shopping', 'bills', 'study', 'health', 'other', 'salary']
TZ = ZoneInfo('Asia/Phnom_Penh')
metadata = MetaData()
transactions = Table('transactions', metadata,
    Column('id', Integer, primary_key=True), Column('user_id', BigInteger, nullable=False, index=True),
    Column('kind', String(10), nullable=False), Column('amount', BigInteger, nullable=False),
    Column('currency', String(3), nullable=False), Column('category', String(20), nullable=False),
    Column('spending_type', String(12)),
    Column('account', String(20), nullable=False), Column('note', String(300), nullable=False),
    Column('day', Date, nullable=False), Column('request_id', String(64), nullable=False),
    UniqueConstraint('user_id', 'request_id'))
budgets = Table('budgets', metadata,
    Column('id', Integer, primary_key=True), Column('user_id', BigInteger, nullable=False),
    Column('month', String(7), nullable=False), Column('currency', String(3), nullable=False),
    Column('amount', BigInteger, nullable=False), UniqueConstraint('user_id', 'month', 'currency'))
spending_budgets = Table('spending_type_budgets', metadata,
    Column('id', Integer, primary_key=True), Column('user_id', BigInteger, nullable=False),
    Column('month', String(7), nullable=False), Column('currency', String(3), nullable=False),
    Column('spending_type', String(12), nullable=False), Column('amount', BigInteger, nullable=False),
    UniqueConstraint('user_id', 'month', 'currency', 'spending_type'))

access_requests = Table('access_requests', metadata,
    Column('user_id', BigInteger, primary_key=True),
    Column('name', String(200), nullable=False),
    Column('status', String(20), nullable=False),
    Column('request_key', String(32), nullable=False, unique=True),
    Column('notified_at', BigInteger, nullable=False, default=0))

registered_users = Table('registered_users', metadata,
    Column('user_id', BigInteger, primary_key=True), Column('name', String(200), nullable=False),
    Column('last_seen', BigInteger, nullable=False))
admin_actions = Table('admin_actions', metadata,
    Column('key', String(32), primary_key=True), Column('target_id', BigInteger, nullable=False),
    Column('action', String(20), nullable=False), Column('expires_at', BigInteger, nullable=False))
admin_audit = Table('admin_audit', metadata,
    Column('id', Integer, primary_key=True), Column('admin_id', BigInteger, nullable=False),
    Column('target_id', BigInteger, nullable=False), Column('action', String(20), nullable=False),
    Column('at', BigInteger, nullable=False))

savings_goals = Table('savings_goals', metadata,
    Column('id', Integer, primary_key=True), Column('user_id', BigInteger, nullable=False, index=True),
    Column('title', String(80), nullable=False), Column('currency', String(3), nullable=False),
    Column('target', BigInteger, nullable=False), Column('saved', BigInteger, nullable=False),
    Column('version', Integer, nullable=False, default=1), Column('request_id', String(64), nullable=False),
    UniqueConstraint('user_id','request_id'))

budget_alerts = Table('budget_alerts', metadata,
    Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False),
    Column('month',String(7),nullable=False),Column('currency',String(3),nullable=False),
    Column('level',Integer,nullable=False),UniqueConstraint('user_id','month','currency','level'))


delete_batches = Table('delete_batches', metadata,
    Column('token', String(32), primary_key=True), Column('user_id', BigInteger, nullable=False),
    Column('ids_json', Text, nullable=False), Column('expires_at', BigInteger, nullable=False))


personal_tables = define_tables(metadata)

def validate_init_data(raw, token, now=None):
    """Never trust initDataUnsafe or a user ID from a request body."""
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError()
        received = data.pop('hash')
        check = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
        secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received):
            raise ValueError()
        age = (time.time() if now is None else now) - int(data['auth_date'])
        if not -30 <= age <= 3600:
            raise ValueError()
        user = json.loads(data['user'])
        if type(user['id']) is not int or user['id'] <= 0:
            raise ValueError()
        return user
    except (ValueError, KeyError, TypeError):
        abort(401, 'Session expired or invalid. Close and reopen the Mini App from Telegram.')


def amount_units(value, currency):
    if currency not in ('USD', 'KHR'):
        abort(400, 'Invalid currency')
    try:
        number = Decimal(str(value))
        scaled = number * (100 if currency == 'USD' else 1)
        if not scaled.is_finite() or scaled <= 0 or scaled > 10**12 or scaled != scaled.to_integral_value():
            raise ValueError()
        return int(scaled)
    except (DecimalException, ValueError, TypeError):
        abort(400, 'Enter a positive amount: whole riel or up to 2 decimal places for USD.')


def month_value(value):
    try:
        if not 2000 <= date.fromisoformat(value + '-01').year <= 2100 or date.fromisoformat(value + '-01').strftime('%Y-%m') != value:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        abort(400, 'Invalid month')


def create_app(config=None):
    app = Flask(__name__, static_folder='static')
    app.config.update(BOT_TOKEN=os.getenv('BOT_TOKEN', ''), APP_URL=os.getenv('APP_URL', '').rstrip('/'),
                      WEBHOOK_SECRET=os.getenv('WEBHOOK_SECRET', ''),
                      ALLOWED_USER_IDS=os.getenv('ALLOWED_USER_IDS', ''),
                      ADMIN_USER_ID=os.getenv('ADMIN_USER_ID', ''),
                      DATABASE_URL=os.getenv('DATABASE_URL', 'sqlite:///money.db'), MAX_CONTENT_LENGTH=3*1024*1024)
    if config:
        app.config.update(config)
    url = app.config['DATABASE_URL']
    if url.startswith(('postgres://', 'postgresql://')):
        url = 'postgresql+psycopg://' + url.split('://', 1)[1]
    engine = create_engine(url, pool_pre_ping=True)
    metadata.create_all(engine)
    # Safe additive migration for existing databases created before spending classification.
    if 'spending_type' not in {column['name'] for column in inspect(engine).get_columns('transactions')}:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE transactions ADD COLUMN spending_type VARCHAR(12)'))
    app.extensions['engine'] = engine
    allowed = {int(x.strip()) for x in app.config['ALLOWED_USER_IDS'].split(',') if x.strip()}

    admin = int(app.config['ADMIN_USER_ID'] or 0)

    def remember_user(user):
        uid = user.get('id')
        if type(uid) is not int or uid <= 0:
            return
        if engine.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert
        values = {'user_id': uid, 'name': str(user.get('first_name', 'User'))[:200], 'last_seen': int(time.time())}
        stmt = upsert(registered_users).values(**values)
        with engine.begin() as conn:
            conn.execute(stmt.on_conflict_do_update(index_elements=['user_id'], set_={
                'name': values['name'], 'last_seen': values['last_seen']}))

    for uid in allowed | ({admin} if admin else set()):
        # Seed configured IDs without overwriting a previously known display name.
        with engine.connect() as conn:
            known = conn.execute(select(registered_users.c.user_id).where(registered_users.c.user_id == uid)).first()
        if not known:
            remember_user({'id': uid})

    def has_access(uid):
        if uid == admin:
            return True
        with engine.connect() as conn:
            status = conn.execute(select(access_requests.c.status).where(access_requests.c.user_id == uid)).scalar()
        # Explicit admin decisions override the legacy environment allowlist.
        if status:
            return status == 'approved'
        return uid in allowed

    def telegram(method, payload):
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{app.config['BOT_TOKEN']}/{method}",
                json=payload, timeout=10)
            return response.ok and response.json().get('ok', False)
        except (requests.RequestException, ValueError):
            return False

    admin_ui = AdminPanel(engine, admin, allowed,
        (registered_users, access_requests, transactions, budgets, admin_actions, admin_audit, savings_goals), telegram, app.config)

    def menu_keyboard(uid):
        rows = [[{'text': 'ðŸ’° MyMoney'}, {'text': 'ðŸ“Š ážŸáž„áŸ’ážáŸáž” / Summary'}],
                [{'text': 'ðŸ’¸ ážáŸ’áž„áŸƒáž“áŸáŸ‡áž¢áž¶áž…áž…áž¶áž™ / Daily allowance'}],
                [{'text': 'âž• áž…áŸ†ážŽáž¶áž™ / Expense'}, {'text': 'ðŸ’µ áž…áŸ†ážŽáž¼áž› / Income'}],
                [{'text': 'ðŸ“… ážšáž”áž¶áž™áž€áž¶ážšážŽáŸáž”áŸ’ážšáž…áž¶áŸ†áž†áŸ’áž“áž¶áŸ† / Yearly report'}, {'text': 'âš™ï¸ ážážœáž·áž€áž¶áž”áŸ’ážšáž…áž¶áŸ†ážáŸ‚ / Monthly budget'}],
                [{'text': 'ðŸŽ¯ áž‚áŸ„áž›ážŠáŸ…ážŸáž“áŸ’ážŸáŸ† / Savings goals'}],
                [{'text': 'ðŸ†” My ID'}, {'text': 'â“ Help'}]]
        if uid == admin and admin:
            rows.append([{'text': 'ðŸ›¡ Admin'}, {'text': 'â³ Requests'}])
        elif not has_access(uid):
            rows.insert(0, [{'text': 'ðŸ”“ Request access'}])
        rows.append([{'text': 'âœ• áž”áž·áž‘ Menu / Close menu'}])
        return {'keyboard': rows, 'resize_keyboard': True, 'is_persistent': True}

    def open_buttons(action=''):
        suffix = '?action=' + action if action else ''
        return {'inline_keyboard': [[{'text': 'ðŸ’° áž”áž¾áž€ / Open MyMoney',
            'web_app': {'url': app.config['APP_URL'] + suffix}}]]}

    def personal_summary(uid, period):
        today = datetime.now(TZ).date()
        if period == 'allowance':
            month = today.strftime('%Y-%m')
            month_start = today.replace(day=1)
            next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            days_left = (next_month - today).days
            with engine.connect() as conn:
                limits = conn.execute(select(budgets.c.currency, budgets.c.amount).where(
                    budgets.c.user_id == uid, budgets.c.month == month)).all()
                expenses = conn.execute(select(transactions.c.currency, func.sum(transactions.c.amount)).where(
                    transactions.c.user_id == uid, transactions.c.kind == 'expense',
                    transactions.c.day >= month_start, transactions.c.day < next_month
                ).group_by(transactions.c.currency)).all()
            text = f'ðŸ’¸ ážáŸ’áž„áŸƒáž“áŸáŸ‡áž¢áž¶áž…áž…áž¶áž™áž”áž¶áž“ / Spendable today\n{month} Â· {days_left} ážáŸ’áž„áŸƒáž“áŸ…ážŸáž›áŸ‹ ážšáž¶áž”áŸ‹áž‘áž¶áŸ†áž„ážáŸ’áž„áŸƒáž“áŸáŸ‡ / days left including today\n'
            if not limits:
                text += '\náž˜áž·áž“áž‘áž¶áž“áŸ‹áž€áŸ†ážŽážáŸ‹ážážœáž·áž€áž¶ážáŸ‚áž“áŸáŸ‡áž‘áŸáŸ” áž”áž¾áž€ MyMoney ážŠáž¾áž˜áŸ’áž”áž¸áž€áŸ†ážŽážáŸ‹ážážœáž·áž€áž¶áŸ”\nSet a monthly budget in MyMoney first.'
            else:
                for currency in ('KHR', 'USD'):
                    limit = next((amount for cur, amount in limits if cur == currency), None)
                    if limit is None:
                        continue
                    spent = next((amount or 0 for cur, amount in expenses if cur == currency), 0)
                    remaining = max(0, limit - spent)
                    daily = remaining // days_left
                    text += f'\n{currency}\náž“áŸ…ážŸáž›áŸ‹ / Left: {display_money(remaining,currency)}\nážáŸ’áž„áŸƒáž“áŸáŸ‡áž¢áž¶áž…áž…áž¶áž™ / Daily amount: {display_money(daily,currency)}'
                    if remaining == 0:
                        text += '\náž”áž¶áž“áž”áŸ’ážšáž¾ážážœáž·áž€áž¶ážáŸ‚áž“áŸáŸ‡áž¢ážŸáŸ‹áž áž¾áž™ / Monthly budget used.'
            return {'text': text, 'reply_markup': open_buttons()}
        start = today if period == 'today' else today - timedelta(days=today.weekday()) if period == 'week' else today.replace(day=1)
        with engine.connect() as conn:
            totals = conn.execute(select(transactions.c.currency, transactions.c.kind, func.sum(transactions.c.amount))
                .where(transactions.c.user_id == uid, transactions.c.day >= start, transactions.c.day <= today)
                .group_by(transactions.c.currency, transactions.c.kind)).all()
        text = f'ðŸ“Š ážŸáž„áŸ’ážáŸáž” / Summary\n{start} â†’ {today}\n'
        for currency in ('KHR', 'USD'):
            income = next((amount for cur, kind, amount in totals if cur == currency and kind == 'income'), 0)
            expense = next((amount for cur, kind, amount in totals if cur == currency and kind == 'expense'), 0)
            text += f'\n{currency}\náž…áŸ†ážŽáž¼áž› / Income: {display_money(income,currency)}\náž…áŸ†ážŽáž¶áž™ / Expenses: {display_money(expense,currency)}\nNet: {display_money(income-expense,currency)}\n'
        return {'text': text, 'reply_markup': {'inline_keyboard': [[
            {'text': 'ážáŸ’áž„áŸƒáž“áŸáŸ‡ / Today', 'callback_data': 'summary:today'},
            {'text': 'ážŸáž”áŸ’ážŠáž¶áž áŸ / Week', 'callback_data': 'summary:week'},
            {'text': 'ážáŸ‚ / Month', 'callback_data': 'summary:month'}],
            [{'text': 'ðŸ’¸ ážáŸ’áž„áŸƒáž“áŸáŸ‡áž¢áž¶áž…áž…áž¶áž™ / Spendable today', 'callback_data': 'summary:allowance'}],
            [{'text': 'ðŸ“ˆ áž€áŸ’ážšáž¶áž áŸ’ážœ / Charts', 'web_app': {'url': app.config['APP_URL']}}]]}}

    def budget_warning(uid, month, currency):
        # Notifications only concern the current month, never historical imports.
        if month != datetime.now(TZ).strftime('%Y-%m'):
            return
        start=date.fromisoformat(month+'-01')
        end=date(start.year+(start.month==12),start.month%12+1,1)
        with engine.connect() as conn:
            limit=conn.execute(select(budgets.c.amount).where(budgets.c.user_id==uid,
                budgets.c.month==month,budgets.c.currency==currency)).scalar()
            if not limit:
                return
            spent=conn.execute(select(func.coalesce(func.sum(transactions.c.amount),0)).where(
                transactions.c.user_id==uid,transactions.c.kind=='expense',transactions.c.currency==currency,
                transactions.c.day>=start,transactions.c.day<end)).scalar()
        level=100 if spent>=limit else 80 if spent*100>=limit*80 else 0
        if not level:
            return
        try:
            with engine.begin() as conn:
                # Don't send a lower-tier alert after a higher-tier one was already delivered.
                higher=conn.execute(select(budget_alerts.c.id).where(budget_alerts.c.user_id==uid,
                    budget_alerts.c.month==month,budget_alerts.c.currency==currency,budget_alerts.c.level>=level)).first()
                if higher:
                    return
                alert_id=conn.execute(insert(budget_alerts).values(user_id=uid,month=month,currency=currency,level=level)).inserted_primary_key[0]
        except IntegrityError:
            return
        title='ðŸš¨ ážŠáž›áŸ‹ áž¬áž›áž¾ážŸážážœáž·áž€áž¶ / Budget reached or exceeded' if level==100 else 'âš ï¸ áž”áŸ’ážšáž¾ážážœáž·áž€áž¶ážŠáž›áŸ‹ 80% / Budget usage reached 80%'
        sent=telegram('sendMessage',{'chat_id':uid,'text':f'{title}\n{month}\náž…áŸ†ážŽáž¶áž™ / Spent: {display_money(spent,currency)}\nážážœáž·áž€áž¶ / Limit: {display_money(limit,currency)}',
            'reply_markup':open_buttons()})
        if not sent:
            with engine.begin() as conn:
                conn.execute(delete(budget_alerts).where(budget_alerts.c.id==alert_id))

    def access_buttons(row):
        key = row['request_key']
        return {'inline_keyboard': [[
            {'text': 'âœ… áž¢áž“áž»áž‰áŸ’áž‰áž¶áž / Approve', 'callback_data': 'approve:' + key},
            {'text': 'âŒ áž”ážŠáž·ážŸáŸáž’ / Reject', 'callback_data': 'reject:' + key}]]}

    def notify_admin(row):
        return telegram('sendMessage', {
            'chat_id': admin,
            'text': f"ðŸ”“ ážŸáŸ†ážŽáž¾áž…áž¼áž›áž”áŸ’ážšáž¾ / Access request\nážˆáŸ’áž˜áŸ„áŸ‡ / Name: {row['name']}\nTelegram ID: {row['user_id']}",
            'reply_markup': access_buttons(row)})

    def request_access(user):
        uid = user['id']
        if has_access(uid):
            return 'âœ… áž¢áŸ’áž“áž€áž˜áž¶áž“ážŸáž·áž‘áŸ’áž’áž·ážšáž½áž…áž áž¾áž™ / Already allowed. Send /start.'
        if not admin:
            return 'âš™ï¸ Admin not configured. Send /id and contact the owner.'
        name = str(user.get('first_name', 'User'))[:200]
        if engine.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert
        with engine.begin() as conn:
            conn.execute(upsert(access_requests).values(user_id=uid, name=name,
                status='pending', request_key=uuid.uuid4().hex, notified_at=0
                ).on_conflict_do_nothing(index_elements=['user_id']))
            row = conn.execute(select(access_requests).where(access_requests.c.user_id == uid)).mappings().one()
            if row['status'] in ('rejected', 'revoked'):
                return 'âŒ ážŸáŸ†ážŽáž¾ážáŸ’ážšáž¼ážœáž”áž¶áž“áž”ážŠáž·ážŸáŸáž’ / Request rejected. Contact the owner.'
            if row['status'] == 'approved':
                return 'âœ… áž¢áŸ’áž“áž€áž˜áž¶áž“ážŸáž·áž‘áŸ’áž’áž·ážšáž½áž…áž áž¾áž™ / Already allowed. Send /start.'
            now = int(time.time())
            # Atomic claim prevents repeated taps/concurrent workers from spamming admin.
            claimed = conn.execute(update(access_requests).where(
                access_requests.c.user_id == uid, access_requests.c.status == 'pending',
                access_requests.c.notified_at <= now - 60).values(notified_at=now)).rowcount
        if claimed and not notify_admin(row):
            with engine.begin() as conn:
                conn.execute(update(access_requests).where(access_requests.c.user_id == uid,
                    access_requests.c.notified_at == now).values(notified_at=0))
            return 'â³ ážŸáŸ†ážŽáž¾áž”áž¶áž“ážšáž€áŸ’ážŸáž¶áž‘áž»áž€ / Request saved, but admin notification failed. Admin can send /requests.'
        return 'â³ ážŸáŸ†ážŽáž¾áž”áž¶áž“ážšáž€áŸ’ážŸáž¶áž‘áž»áž€áŸ” ážŸáž¼áž˜ážšáž„áŸ‹áž…áž¶áŸ† Admin / Request pending admin approval.'

    def auth(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not app.config['BOT_TOKEN'] or not (allowed or admin):
                abort(503, 'Owner must configure BOT_TOKEN and ADMIN_USER_ID (or ALLOWED_USER_IDS).')
            header = request.headers.get('Authorization', '')
            if not header.startswith('tma '):
                abort(401, 'Open this app using the Telegram bot menu.')
            g.user = validate_init_data(header[4:], app.config['BOT_TOKEN'])
            remember_user(g.user)
            if not has_access(g.user['id']):
                abort(403, 'Access disabled. Close the Mini App and send /request to the bot. ážŸáž¼áž˜áž•áŸ’áž‰áž¾ /request áž‘áŸ… BotáŸ”')
            return fn(*args, **kwargs)
        return wrapped

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    @app.errorhandler(503)
    def error(e):
        return jsonify(error=e.description), e.code

    @app.after_request
    def security(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:; object-src 'none'; base-uri 'self'"
        return response

    @app.get('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/health')
    def health():
        return {'ok': True}

    def json_body():
        if len(request.get_data()) > 16384:
            abort(413, 'JSON request too large')
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, 'Expected a JSON object')
        return body

    def entry(body):
        try:
            kind = body['kind']
            category = body['category']
            account = body['account']
            currency = body['currency']
            day = date.fromisoformat(body['day'])
            note = body.get('note', '')
            builtin = category in CATEGORIES
            custom = False
            if isinstance(category, str) and not builtin and kind in ('expense', 'income'):
                custom_table = personal_tables['custom_categories']
                with engine.connect() as conn:
                    category_kind = conn.execute(select(custom_table.c.kind).where(
                        custom_table.c.user_id == g.user['id'], custom_table.c.key == category)).scalar_one_or_none()
                custom = category_kind in (kind, 'both')
            builtin_allowed = (kind == 'income' and category in ('salary', 'other')) or (
                kind == 'expense' and category in CATEGORIES and category != 'salary')
            if kind not in ('expense', 'income') or not (builtin_allowed or custom) or account not in ('cash', 'bank'):
                raise ValueError()
            if not isinstance(note, str) or len(note) > 300 or day.year < 2000 or day > datetime.now(TZ).date():
                raise ValueError()
            spending_type = body.get('spending_type', 'essential' if kind == 'expense' else None)
            if kind == 'expense' and spending_type not in ('essential', 'want', 'none'):
                raise ValueError()
            if kind == 'income':
                spending_type = None
            return dict(kind=kind, category=category, account=account, currency=currency,
                        spending_type=spending_type,
                        amount=amount_units(body['amount'], currency), day=day, note=note.strip())
        except (KeyError, ValueError, TypeError):
            abort(400, 'Check transaction fields, date and note (maximum 300 characters).')

    def serialize(row):
        result = dict(row)
        result.pop('user_id', None)
        result.pop('request_id', None)
        if 'day' in result:
            result['day'] = result['day'].isoformat()
        return result

    @app.get('/api/data')
    @auth
    def data():
        month = month_value(request.args.get('month', datetime.now(TZ).strftime('%Y-%m')))
        start = date.fromisoformat(month + '-01')
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
        with engine.connect() as conn:
            rows = conn.execute(select(transactions).where(transactions.c.user_id == g.user['id'],
                transactions.c.day >= start, transactions.c.day < end).order_by(transactions.c.day.desc(), transactions.c.id.desc())).mappings().all()
            limits = conn.execute(select(budgets).where(budgets.c.user_id == g.user['id'], budgets.c.month == month)).mappings().all()
            type_limits = conn.execute(select(spending_budgets).where(spending_budgets.c.user_id == g.user['id'], spending_budgets.c.month == month)).mappings().all()
        with engine.connect() as conn:
            profile_name = conn.execute(select(personal_tables['profiles'].c.name).where(personal_tables['profiles'].c.user_id == g.user['id'])).scalar_one_or_none()
        return jsonify(user={'name': profile_name or (os.getenv('ADMIN_DISPLAY_NAME', 'Thearith') if g.user['id'] == admin else g.user.get('first_name', 'Friend')), 'id': g.user['id'], 'is_admin': g.user['id'] == admin}, today=datetime.now(TZ).date().isoformat(),
                       transactions=[serialize(r) for r in rows], budgets=[serialize(r) for r in limits],
                       spending_budgets=[serialize(r) for r in type_limits])

    @app.get('/api/summary')
    @auth
    def summary():
        period = request.args.get('period', 'today')
        if period not in ('today', 'week', 'month'):
            abort(400, 'Invalid summary period')
        today = datetime.now(TZ).date()
        start = today if period == 'today' else today - timedelta(days=today.weekday()) if period == 'week' else today.replace(day=1)
        with engine.connect() as conn:
            rows = conn.execute(select(transactions.c.currency, transactions.c.kind, func.sum(transactions.c.amount))
                .where(transactions.c.user_id == g.user['id'], transactions.c.day >= start, transactions.c.day <= today)
                .group_by(transactions.c.currency, transactions.c.kind)).all()
        return {'start': start.isoformat(), 'end': today.isoformat(), 'totals': [
            {'currency': c, 'kind': k, 'amount': int(a)} for c,k,a in rows]}

    @app.get('/api/yearly-summary')
    @auth
    def yearly_summary():
        raw_year = request.args.get('year', str(datetime.now(TZ).year))
        try:
            year = int(raw_year)
            if str(year) != raw_year or not 2000 <= year <= 2100:
                raise ValueError()
        except (TypeError, ValueError):
            abort(400, 'Invalid year')
        start, end = date(year, 1, 1), date(year + 1, 1, 1)
        with engine.connect() as conn:
            totals = conn.execute(select(transactions.c.currency, transactions.c.kind,
                    func.sum(transactions.c.amount)).where(transactions.c.user_id == g.user['id'],
                    transactions.c.day >= start, transactions.c.day < end)
                .group_by(transactions.c.currency, transactions.c.kind)).all()
            if engine.dialect.name == 'sqlite':
                monthly_rows = conn.execute(select(func.strftime('%Y-%m', transactions.c.day),
                        transactions.c.currency, transactions.c.kind, func.sum(transactions.c.amount))
                    .where(transactions.c.user_id == g.user['id'], transactions.c.day >= start,
                           transactions.c.day < end)
                    .group_by(func.strftime('%Y-%m', transactions.c.day), transactions.c.currency,
                              transactions.c.kind)).all()
                monthly = monthly_rows
            else:
                # Group by the actual month-start date. Grouping by to_char(day, ...)
                # while selecting that expression can become a parameterized format
                # expression in SQLAlchemy/psycopg, which PostgreSQL does not consider
                # equivalent to the selected expression for GROUP BY validation.
                monthly_rows = conn.execute(select(func.date_trunc('month', transactions.c.day),
                        transactions.c.currency, transactions.c.kind, func.sum(transactions.c.amount))
                    .where(transactions.c.user_id == g.user['id'], transactions.c.day >= start,
                           transactions.c.day < end)
                    .group_by(func.date_trunc('month', transactions.c.day), transactions.c.currency,
                              transactions.c.kind)).all()
                monthly = [(month.strftime('%Y-%m'), currency, kind, amount)
                           for month, currency, kind, amount in monthly_rows]
            categories = conn.execute(select(transactions.c.category, transactions.c.currency,
                    func.sum(transactions.c.amount)).where(transactions.c.user_id == g.user['id'],
                    transactions.c.day >= start, transactions.c.day < end,
                    transactions.c.kind == 'expense').group_by(transactions.c.category,
                    transactions.c.currency)).all()
            spending = conn.execute(select(func.coalesce(transactions.c.spending_type, 'essential'),
                    transactions.c.currency, func.sum(transactions.c.amount)).where(
                    transactions.c.user_id == g.user['id'], transactions.c.day >= start,
                    transactions.c.day < end, transactions.c.kind == 'expense').group_by(
                    func.coalesce(transactions.c.spending_type, 'essential'),
                    transactions.c.currency)).all()
        return {'year': year,
            'totals': [{'currency': c, 'kind': k, 'amount': int(a)} for c,k,a in totals],
            'monthly': [{'month': m, 'currency': c, 'kind': k, 'amount': int(a)} for m,c,k,a in monthly],
            'categories': [{'category': c, 'currency': cur, 'amount': int(a)} for c,cur,a in categories],
            'spending_types': [{'type': t, 'currency': c, 'amount': int(a)} for t,c,a in spending]}

    @app.post('/api/transactions/delete-preview')
    @auth
    def preview_delete():
        body = json_body()
        scope = body.get('scope')
        query = select(transactions.c.id, transactions.c.request_id).where(transactions.c.user_id == g.user['id'])
        requested = None
        if scope == 'selected':
            requested = body.get('ids')
            if not isinstance(requested, list) or not 1 <= len(requested) <= 1000 or any(type(i) is not int or i <= 0 for i in requested):
                abort(400, 'Select 1â€“1000 valid entries.')
            requested = set(requested)
            query = query.where(transactions.c.id.in_(requested))
        elif scope != 'all':
            abort(400, 'Invalid deletion scope.')
        with engine.begin() as conn:
            snapshot = list(conn.execute(query))
            ids = [row.id for row in snapshot]
            if requested is not None and set(ids) != requested:
                abort(404, 'An entry is unavailable. Refresh your history.')
            now = int(time.time())
            conn.execute(delete(delete_batches).where(delete_batches.c.expires_at < now))
            conn.execute(delete(delete_batches).where(delete_batches.c.user_id == g.user['id']))
            token = uuid.uuid4().hex if ids else None
            if ids:
                conn.execute(insert(delete_batches).values(token=token,user_id=g.user['id'],ids_json=json.dumps([row.request_id for row in snapshot]),expires_at=now+300))
        return {'token':token,'count':len(ids),'scope':scope}

    @app.post('/api/transactions/delete-confirm')
    @auth
    def confirm_delete():
        body = json_body()
        token = body.get('token')
        if body.get('confirmation') != 'DELETE' or not isinstance(token,str) or len(token)!=32:
            abort(400, 'Type DELETE to confirm.')
        with engine.begin() as conn:
            batch = conn.execute(delete(delete_batches).where(delete_batches.c.token==token,
                delete_batches.c.user_id==g.user['id'],delete_batches.c.expires_at>=int(time.time()))
                .returning(delete_batches.c.ids_json)).scalar_one_or_none()
            if batch is None:
                abort(409, 'Confirmation expired or already used. Refresh your history.')
            ids = json.loads(batch)
            count = 0
            for start in range(0,len(ids),500):
                deleted_rows = conn.execute(delete(transactions).where(transactions.c.user_id==g.user['id'],
                    transactions.c.request_id.in_(ids[start:start+500])).returning(*transactions.c)).mappings().all()
                archive_rows(conn, deleted_rows, personal_tables)
                count += len(deleted_rows)
        return {'deleted':count}

    @app.get('/api/goals')
    @auth
    def list_goals():
        with engine.connect() as conn:
            rows = conn.execute(select(savings_goals).where(savings_goals.c.user_id == g.user['id'])
                .order_by(savings_goals.c.id.desc())).mappings().all()
        return {'goals':[serialize(row) for row in rows]}

    def goal_values(body):
        title = body.get('title')
        currency = body.get('currency')
        if not isinstance(title,str) or not title.strip() or len(title)>80:
            abort(400,'Goal title must have 1â€“80 characters.')
        target = amount_units(body.get('target'), currency)
        raw_saved = body.get('saved')
        try:
            zero = Decimal(str(raw_saved)) == 0
        except DecimalException:
            zero = False
        saved = 0 if zero else amount_units(raw_saved,currency)
        return dict(title=title.strip(),currency=currency,target=target,saved=saved)

    @app.post('/api/goals')
    @auth
    def add_goal():
        body = json_body()
        values = goal_values(body)
        key = body.get('request_id','')
        if not isinstance(key,str) or not 8<=len(key)<=64:
            abort(400,'Missing request ID')
        try:
            with engine.begin() as conn:
                result=conn.execute(insert(savings_goals).values(**values,user_id=g.user['id'],version=1,request_id=key))
                identity=result.inserted_primary_key[0]
        except IntegrityError:
            with engine.connect() as conn:
                identity=conn.execute(select(savings_goals.c.id).where(savings_goals.c.user_id==g.user['id'],savings_goals.c.request_id==key)).scalar_one()
        return {'id':identity},201

    @app.put('/api/goals/<int:identity>')
    @auth
    def edit_goal(identity):
        body=json_body()
        values=goal_values(body)
        version=body.get('version')
        if type(version) is not int or version<1:
            abort(400,'Invalid goal version')
        with engine.begin() as conn:
            current=conn.execute(select(savings_goals).where(savings_goals.c.id==identity,savings_goals.c.user_id==g.user['id'])).mappings().first()
            if not current:
                abort(404,'Goal not found')
            if current['currency'] != values['currency']:
                abort(400,'Goal currency cannot change. Create a new goal instead.')
            changed=conn.execute(update(savings_goals).where(savings_goals.c.id==identity,
                savings_goals.c.user_id==g.user['id'],savings_goals.c.version==version)
                .values(**values,version=version+1)).rowcount
            if not changed:
                abort(409,'Goal changed elsewhere. Close this form, refresh, and try again.')
        return {'ok':True}

    @app.delete('/api/goals/<int:identity>')
    @auth
    def delete_goal(identity):
        with engine.begin() as conn:
            changed=conn.execute(delete(savings_goals).where(savings_goals.c.id==identity,savings_goals.c.user_id==g.user['id'])).rowcount
            if not changed:
                abort(404,'Goal not found')
        return {'ok':True}

    @app.post('/api/transactions')
    @auth
    def add():
        body = json_body()
        values = entry(body)
        key = body.get('request_id', '')
        if not isinstance(key, str) or not 8 <= len(key) <= 64:
            abort(400, 'Missing request ID')
        with engine.connect() as conn:
            if conn.execute(select(personal_tables['trash'].c.id).where(personal_tables['trash'].c.user_id==g.user['id'],personal_tables['trash'].c.request_id==key)).first():
                abort(409, 'This entry is in trash. Restore it instead of retrying its creation.')
        try:
            with engine.begin() as conn:
                result = conn.execute(insert(transactions).values(**values, user_id=g.user['id'], request_id=key))
                identity = result.inserted_primary_key[0]
        except IntegrityError:
            with engine.connect() as conn:
                identity = conn.execute(select(transactions.c.id).where(transactions.c.user_id == g.user['id'], transactions.c.request_id == key)).scalar_one()
        if values['kind']=='expense':
            budget_warning(g.user['id'],values['day'].strftime('%Y-%m'),values['currency'])
        return {'id': identity}, 201

    @app.put('/api/transactions/<int:identity>')
    @auth
    def edit(identity):
        values = entry(json_body())
        with engine.begin() as conn:
            result = conn.execute(update(transactions).where(transactions.c.id == identity, transactions.c.user_id == g.user['id']).values(**values))
            if not result.rowcount:
                abort(404, 'Transaction not found')
        if values['kind']=='expense':
            budget_warning(g.user['id'],values['day'].strftime('%Y-%m'),values['currency'])
        return {'ok': True}

    @app.delete('/api/transactions/<int:identity>')
    @auth
    def remove(identity):
        with engine.begin() as conn:
            removed = conn.execute(delete(transactions).where(transactions.c.id == identity, transactions.c.user_id == g.user['id']).returning(*transactions.c)).mappings().all()
            if not removed:
                abort(404, 'Transaction not found')
            archive_rows(conn, removed, personal_tables)
        return {'ok': True}

    @app.put('/api/budget')
    @auth
    def budget():
        body = json_body()
        month = month_value(body.get('month', ''))
        currency = body.get('currency')
        amount = amount_units(body.get('amount'), currency)
        # Dialect-native upsert is safe across concurrent requests.
        if engine.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert
        stmt = upsert(budgets).values(user_id=g.user['id'], month=month, currency=currency, amount=amount)
        stmt = stmt.on_conflict_do_update(index_elements=['user_id', 'month', 'currency'], set_={'amount': amount})
        with engine.begin() as conn:
            conn.execute(stmt)
        budget_warning(g.user['id'],month,currency)
        return {'ok': True, 'month': month, 'currency': currency, 'amount': amount}

    @app.put('/api/spending-budgets')
    @auth
    def set_spending_budget():
        body = json_body()
        month = month_value(body.get('month', ''))
        currency = body.get('currency')
        spending_type = body.get('spending_type')
        if spending_type not in ('essential', 'want'):
            abort(400, 'Choose essential or want spending.')
        amount = amount_units(body.get('amount'), currency)
        if engine.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert
        stmt = upsert(spending_budgets).values(user_id=g.user['id'], month=month,
            currency=currency, spending_type=spending_type, amount=amount)
        stmt = stmt.on_conflict_do_update(index_elements=['user_id', 'month', 'currency', 'spending_type'],
            set_={'amount': amount})
        with engine.begin() as conn:
            conn.execute(stmt)
        return {'ok': True, 'month': month, 'currency': currency,
                'spending_type': spending_type, 'amount': amount}

    @app.delete('/api/spending-budgets')
    @auth
    def remove_spending_budget():
        body = json_body()
        month = month_value(body.get('month', ''))
        currency = body.get('currency')
        spending_type = body.get('spending_type')
        if currency not in ('USD', 'KHR') or spending_type not in ('essential', 'want'):
            abort(400, 'Invalid currency or spending type.')
        with engine.begin() as conn:
            conn.execute(delete(spending_budgets).where(
                spending_budgets.c.user_id == g.user['id'], spending_budgets.c.month == month,
                spending_budgets.c.currency == currency,
                spending_budgets.c.spending_type == spending_type))
        return {'ok': True}

    @app.get('/api/export')
    @auth
    def export():
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(['Date', 'Type', 'Needs or wants', 'Amount', 'Currency', 'Category', 'Account', 'Note'])
        with engine.connect() as conn:
            for r in conn.execute(select(transactions).where(transactions.c.user_id == g.user['id']).order_by(transactions.c.day)).mappings():
                note = r['note']
                if note.lstrip().startswith(('=', '+', '-', '@')) or note.startswith(('\t', '\r', '\n')):
                    note = "'" + note
                writer.writerow([r['day'], r['kind'], r.get('spending_type') or '', str(Decimal(r['amount']) / (100 if r['currency'] == 'USD' else 1)), r['currency'], r['category'], r['account'], note])
        return Response('\ufeff' + out.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename="mymoney.csv"'})

    @app.post('/telegram/webhook')
    def webhook():
        secret = app.config['WEBHOOK_SECRET']
        if not secret or not hmac.compare_digest(request.headers.get('X-Telegram-Bot-Api-Secret-Token', ''), secret):
            abort(403)

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, 'Invalid update')
        callback = body.get('callback_query')
        if callback:
            user = callback.get('from', {})
            uid = user.get('id')
            callback_id = callback.get('id')
            action = callback.get('data', '')
            message = callback.get('message', {})
            chat = message.get('chat', {})
            if chat.get('type') != 'private' or chat.get('id') != uid:
                telegram('answerCallbackQuery', {'callback_query_id': callback_id, 'text': 'Use your private bot chat.'})
                return {'ok': True}
            remember_user(user)
            if action.startswith('summary:'):
                telegram('answerCallbackQuery', {'callback_query_id': callback_id})
                period = action.split(':', 1)[1]
                payload = personal_summary(uid, period) if has_access(uid) and period in ('today','week','month','allowance') else {'text': 'ðŸ”’ Send /request to request access.'}
                telegram('sendMessage', {'chat_id': uid, **payload})
                return {'ok': True}
            if action.startswith('admin:'):
                telegram('answerCallbackQuery', {'callback_query_id': callback_id})
                result = admin_ui.render(uid, action)
                telegram('sendMessage', {'chat_id': uid, **result})
                return {'ok': True}
            if action == 'request_access':
                telegram('answerCallbackQuery', {'callback_query_id': callback_id})
                text = request_access(user)
                telegram('sendMessage', {'chat_id': uid, 'text': text})
                return {'ok': True}
            # Never derive admin identity from callback data or target user ID.
            if not admin or uid != admin:
                telegram('answerCallbackQuery', {'callback_query_id': callback_id, 'text': 'Admin only', 'show_alert': True})
                return {'ok': True}
            operation, _, key = action.partition(':')
            if operation not in ('approve', 'reject') or len(key) != 32:
                telegram('answerCallbackQuery', {'callback_query_id': callback_id, 'text': 'Invalid action'})
                return {'ok': True}
            status = 'approved' if operation == 'approve' else 'rejected'
            with engine.begin() as conn:
                row = conn.execute(select(access_requests).where(access_requests.c.request_key == key)).mappings().first()
                changed = row and conn.execute(update(access_requests).where(
                    access_requests.c.request_key == key, access_requests.c.status == 'pending'
                    ).values(status=status)).rowcount
                if changed:
                    conn.execute(insert(admin_audit).values(admin_id=admin, target_id=row['user_id'], action=operation, at=int(time.time())))
            if not changed:
                telegram('answerCallbackQuery', {'callback_query_id': callback_id, 'text': 'Already handled or unavailable'})
                return {'ok': True}
            telegram('answerCallbackQuery', {'callback_query_id': callback_id, 'text': status.capitalize()})
            delivered = telegram('sendMessage', {'chat_id': row['user_id'], 'text':
                'âœ… áž”áž¶áž“áž¢áž“áž»áž‰áŸ’áž‰áž¶áž / Access approved! Send /start and reopen MyMoney.' if status == 'approved'
                else 'âŒ ážŸáŸ†ážŽáž¾ážáŸ’ážšáž¼ážœáž”áž¶áž“áž”ážŠáž·ážŸáŸáž’ / Access request rejected.'})
            telegram('editMessageText', {'chat_id': admin, 'message_id': message['message_id'],
                'text': f"{status.upper()} â€” {row['name']}\nTelegram ID: {row['user_id']}" +
                ('' if delivered else '\nNotification failed; access decision is saved.'),
                'reply_markup': {'inline_keyboard': []}})
            return {'ok': True}

        message = body.get('message', {})
        chat = message.get('chat', {})
        if chat.get('type') != 'private':
            return {'ok': True}
        user = message.get('from', {})
        uid = user.get('id')
        remember_user(user)
        raw = message.get('text', '').strip()
        aliases = {'ðŸ’° MyMoney':'/open','ðŸ“Š ážŸáž„áŸ’ážáŸáž” / Summary':'/summary',
            'ðŸ’¸ ážáŸ’áž„áŸƒáž“áŸáŸ‡áž¢áž¶áž…áž…áž¶áž™ / Daily allowance':'/allowance',
            'âž• áž…áŸ†ážŽáž¶áž™ / Expense':'/expense','ðŸ’µ áž…áŸ†ážŽáž¼áž› / Income':'/income',
            'ðŸ“… ážšáž”áž¶áž™áž€áž¶ážšážŽáŸáž”áŸ’ážšáž…áž¶áŸ†áž†áŸ’áž“áž¶áŸ† / Yearly report':'/yearly',
            'âš™ï¸ ážážœáž·áž€áž¶áž”áŸ’ážšáž…áž¶áŸ†ážáŸ‚ / Monthly budget':'/budget',
            'ðŸŽ¯ áž‚áŸ„áž›ážŠáŸ…ážŸáž“áŸ’ážŸáŸ† / Savings goals':'/goals',
            'ðŸ†” My ID':'/id','â“ Help':'/help','ðŸ›¡ Admin':'/admin','â³ Requests':'/requests',
            'ðŸ”“ Request access':'/request', 'âœ• áž”áž·áž‘ Menu / Close menu':'/closemenu'}
        command = aliases.get(raw, raw.split(' ')[0].split('@')[0])
        payload = {'chat_id': chat['id']}
        privacy = 'áž¯áž€áž‡áž“áž—áž¶áž–áŸ– Admin áž¢áž¶áž…áž˜áž¾áž›áž‘áž·áž“áŸ’áž“áž“áŸáž™áž áž·ážšáž‰áŸ’áž‰ážœážáŸ’ážáž»áž€áŸ’áž“áž»áž„ Bot áž“áŸáŸ‡áŸ” / Privacy: the owner/admin can review your recorded transactions and budgets.'
        if command == '/closemenu':
            payload['text'] = 'áž”áž¶áž“áž”áž·áž‘ MenuáŸ” áž•áŸ’áž‰áž¾ /menu ážŠáž¾áž˜áŸ’áž”áž¸áž”áž¾áž€ážœáž·áž‰áŸ” / Menu closed. Send /menu to reopen.'
            payload['reply_markup'] = {'remove_keyboard': True}
        elif command == '/id':
            payload['text'] = f'Telegram ID: {uid}'
        elif command in ('/help', '/privacy'):
            payload['text'] = 'ðŸ’° MyMoney\n/start /menu â€” áž”áž„áŸ’áž áž¶áž‰áž”áŸŠáž¼ážáž»áž„ / Show buttons\n/id â€” Telegram ID\n/request â€” ážŸáŸ’áž“áž¾ážŸáž»áŸ†áž…áž¼áž›áž”áŸ’ážšáž¾ / Request access\n/summary â€” ážŸáž„áŸ’ážáŸáž” / Summary\n/allowance â€” ážáŸ’áž„áŸƒáž“áŸáŸ‡áž¢áž¶áž…áž…áž¶áž™áž”áž¶áž“áž”áŸ‰áž»áž“áŸ’áž˜áž¶áž“? / Spendable today\n/yearly â€” ážŸáž„áŸ’ážáŸáž”áž”áŸ’ážšáž…áž¶áŸ†áž†áŸ’áž“áž¶áŸ† / Yearly report\n/budget â€” áž€áŸ†ážŽážáŸ‹ážážœáž·áž€áž¶áž”áŸ’ážšáž…áž¶áŸ†ážáŸ‚ / Monthly limit\n/goals â€” áž‚áŸ„áž›ážŠáŸ…ážŸáž“áŸ’ážŸáŸ† / Savings goals\nExpense / Income â€” open entry form\n\n' + privacy
        elif command == '/request':
            payload['text'] = request_access(user)
        elif command == '/admin':
            payload.update(admin_ui.render(uid, 'admin:home'))
        elif command == '/requests':
            if not admin or uid != admin:
                payload['text'] = 'ðŸ”’ Admin only.'
            else:
                with engine.connect() as conn:
                    pending = conn.execute(select(access_requests).where(
                        access_requests.c.status == 'pending').order_by(access_requests.c.user_id).limit(5)).mappings().all()
                delivered = sum(bool(notify_admin(row)) for row in pending)
                payload['text'] = f'Pending requests sent: {delivered}/{len(pending)}. Approve/reject these, then send /requests for the next batch.' if pending else 'âœ… No pending requests.'
        elif command in ('/start', '/menu'):
            payload['reply_markup'] = menu_keyboard(uid)
            payload['text'] = f'ðŸ’° áž›áž»áž™ážáŸ’áž‰áž»áŸ† / MyMoney\nTelegram ID: {uid}\náž‡áŸ’ážšáž¾ážŸáž”áŸŠáž¼ážáž»áž„ážáž¶áž„áž€áŸ’ážšáŸ„áž˜ / Choose a button below.\n\n' + privacy
            if not has_access(uid):
                payload['text'] += '\nðŸ”’ áž…áž»áž… Request access ážŠáž¾áž˜áŸ’áž”áž¸ážŸáŸ’áž“áž¾ážŸáž»áŸ†ážŸáž·áž‘áŸ’áž’áž·áŸ”'
            # Reply keyboard uses text buttons; Web App opens via an INLINE button
            # so Telegram supplies signed initData for backend authentication.
            telegram('sendMessage', payload)
            if has_access(uid):
                payload = {'chat_id': uid, 'text': 'ðŸ’° áž”áž¾áž€áž€áž˜áŸ’áž˜ážœáž·áž’áž¸ / Open your Mini App', 'reply_markup': open_buttons()}
            else:
                payload = {'chat_id': uid, 'text': 'ðŸ”“ ážŸáŸ’áž“áž¾ážŸáž»áŸ†áž…áž¼áž›áž”áŸ’ážšáž¾ / Request access', 'reply_markup': {
                    'inline_keyboard': [[{'text':'ðŸ”“ Request access','callback_data':'request_access'}]]}}
        elif not has_access(uid):
            payload['text'] = f'ðŸ”’ Access disabled. Telegram ID: {uid}\n' + privacy
            payload['reply_markup'] = {'inline_keyboard': [[{'text':'ðŸ”“ Request access','callback_data':'request_access'}]]}
        elif command == '/summary':
            payload.update(personal_summary(uid, 'month'))
        elif command == '/allowance':
            payload.update(personal_summary(uid, 'allowance'))
        elif command in ('/open','/expense','/income','/budget','/yearly','/goals'):
            payload['text'] = 'ðŸ’° áž…áž»áž…áž”áž¾áž€ / Tap to open'
            action = {'/open':'','/yearly':'reports'}.get(command, command[1:])
            payload['reply_markup'] = open_buttons(action)
        else:
            payload['text'] = 'áž‡áŸ’ážšáž¾ážŸáž”áŸŠáž¼ážáž»áž„ Menu ážŠáž¾áž˜áŸ’áž”áž¸áž€ážáŸ‹ážáŸ’ážšáž¶ / Use the menu buttons. Send /help for instructions.'
        if not telegram('sendMessage', payload):
            return {'error': 'Telegram delivery failed'}, 502
        return {'ok': True}

    register_features(app, engine, transactions, personal_tables, auth, json_body, amount_units, month_value, CATEGORIES)
    return app