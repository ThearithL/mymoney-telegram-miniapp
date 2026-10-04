import csv
import hashlib
import hmac
import io
import json
import os
import time
import uuid
from datetime import date, datetime
from decimal import Decimal, DecimalException
from functools import wraps
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from flask import Flask, abort, g, jsonify, request, send_from_directory, Response
from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, BigInteger,
                        String, Date, UniqueConstraint, select, insert, update, delete)
from sqlalchemy.exc import IntegrityError

load_dotenv()
CATEGORIES = ['food', 'coffee', 'transport', 'shopping', 'bills', 'study', 'health', 'other', 'salary']
TZ = ZoneInfo('Asia/Phnom_Penh')
metadata = MetaData()
transactions = Table('transactions', metadata,
    Column('id', Integer, primary_key=True), Column('user_id', BigInteger, nullable=False, index=True),
    Column('kind', String(10), nullable=False), Column('amount', BigInteger, nullable=False),
    Column('currency', String(3), nullable=False), Column('category', String(20), nullable=False),
    Column('account', String(20), nullable=False), Column('note', String(300), nullable=False),
    Column('day', Date, nullable=False), Column('request_id', String(64), nullable=False),
    UniqueConstraint('user_id', 'request_id'))
budgets = Table('budgets', metadata,
    Column('id', Integer, primary_key=True), Column('user_id', BigInteger, nullable=False),
    Column('month', String(7), nullable=False), Column('currency', String(3), nullable=False),
    Column('amount', BigInteger, nullable=False), UniqueConstraint('user_id', 'month', 'currency'))

access_requests = Table('access_requests', metadata,
    Column('user_id', BigInteger, primary_key=True),
    Column('name', String(200), nullable=False),
    Column('status', String(20), nullable=False),
    Column('request_key', String(32), nullable=False, unique=True),
    Column('notified_at', BigInteger, nullable=False, default=0))


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
                      DATABASE_URL=os.getenv('DATABASE_URL', 'sqlite:///money.db'), MAX_CONTENT_LENGTH=16384)
    if config:
        app.config.update(config)
    url = app.config['DATABASE_URL']
    if url.startswith(('postgres://', 'postgresql://')):
        url = 'postgresql+psycopg://' + url.split('://', 1)[1]
    engine = create_engine(url, pool_pre_ping=True)
    metadata.create_all(engine)
    app.extensions['engine'] = engine
    allowed = {int(x.strip()) for x in app.config['ALLOWED_USER_IDS'].split(',') if x.strip()}

    admin = int(app.config['ADMIN_USER_ID'] or 0)

    def has_access(uid):
        if uid == admin or uid in allowed:
            return True
        with engine.connect() as conn:
            return conn.execute(select(access_requests.c.status).where(
                access_requests.c.user_id == uid)).scalar() == 'approved'

    def telegram(method, payload):
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{app.config['BOT_TOKEN']}/{method}",
                json=payload, timeout=10)
            return response.ok and response.json().get('ok', False)
        except (requests.RequestException, ValueError):
            return False

    def access_buttons(row):
        key = row['request_key']
        return {'inline_keyboard': [[
            {'text': '✅ អនុញ្ញាត / Approve', 'callback_data': 'approve:' + key},
            {'text': '❌ បដិសេធ / Reject', 'callback_data': 'reject:' + key}]]}

    def notify_admin(row):
        return telegram('sendMessage', {
            'chat_id': admin,
            'text': f"🔓 សំណើចូលប្រើ / Access request\nឈ្មោះ / Name: {row['name']}\nTelegram ID: {row['user_id']}",
            'reply_markup': access_buttons(row)})

    def request_access(user):
        uid = user['id']
        if has_access(uid):
            return '✅ អ្នកមានសិទ្ធិរួចហើយ / Already allowed. Send /start.'
        if not admin:
            return '⚙️ Admin not configured. Send /id and contact the owner.'
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
            if row['status'] == 'rejected':
                return '❌ សំណើត្រូវបានបដិសេធ / Request rejected. Contact the owner.'
            if row['status'] == 'approved':
                return '✅ អ្នកមានសិទ្ធិរួចហើយ / Already allowed. Send /start.'
            now = int(time.time())
            # Atomic claim prevents repeated taps/concurrent workers from spamming admin.
            claimed = conn.execute(update(access_requests).where(
                access_requests.c.user_id == uid, access_requests.c.status == 'pending',
                access_requests.c.notified_at <= now - 60).values(notified_at=now)).rowcount
        if claimed and not notify_admin(row):
            with engine.begin() as conn:
                conn.execute(update(access_requests).where(access_requests.c.user_id == uid,
                    access_requests.c.notified_at == now).values(notified_at=0))
            return '⏳ សំណើបានរក្សាទុក / Request saved, but admin notification failed. Admin can send /requests.'
        return '⏳ សំណើបានរក្សាទុក។ សូមរង់ចាំ Admin / Request pending admin approval.'

    def auth(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not app.config['BOT_TOKEN'] or not (allowed or admin):
                abort(503, 'Owner must configure BOT_TOKEN and ADMIN_USER_ID (or ALLOWED_USER_IDS).')
            header = request.headers.get('Authorization', '')
            if not header.startswith('tma '):
                abort(401, 'Open this app using the Telegram bot menu.')
            g.user = validate_init_data(header[4:], app.config['BOT_TOKEN'])
            if not has_access(g.user['id']):
                abort(403, 'Access disabled. Close the Mini App and send /request to the bot. សូមផ្ញើ /request ទៅ Bot។')
            return fn(*args, **kwargs)
        return wrapped

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    @app.errorhandler(503)
    def error(e):
        return jsonify(error=e.description), e.code

    @app.after_request
    def security(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'"
        return response

    @app.get('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/health')
    def health():
        return {'ok': True}

    def json_body():
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
            if kind not in ('expense', 'income') or category not in CATEGORIES or account not in ('cash', 'bank'):
                raise ValueError()
            if not isinstance(note, str) or len(note) > 300 or day.year < 2000 or day > datetime.now(TZ).date():
                raise ValueError()
            return dict(kind=kind, category=category, account=account, currency=currency,
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
        return jsonify(user={'name': g.user.get('first_name', 'Friend')}, today=datetime.now(TZ).date().isoformat(),
                       transactions=[serialize(r) for r in rows], budgets=[serialize(r) for r in limits])

    @app.post('/api/transactions')
    @auth
    def add():
        body = json_body()
        values = entry(body)
        key = body.get('request_id', '')
        if not isinstance(key, str) or not 8 <= len(key) <= 64:
            abort(400, 'Missing request ID')
        try:
            with engine.begin() as conn:
                result = conn.execute(insert(transactions).values(**values, user_id=g.user['id'], request_id=key))
                identity = result.inserted_primary_key[0]
        except IntegrityError:
            with engine.connect() as conn:
                identity = conn.execute(select(transactions.c.id).where(transactions.c.user_id == g.user['id'], transactions.c.request_id == key)).scalar_one()
        return {'id': identity}, 201

    @app.put('/api/transactions/<int:identity>')
    @auth
    def edit(identity):
        values = entry(json_body())
        with engine.begin() as conn:
            result = conn.execute(update(transactions).where(transactions.c.id == identity, transactions.c.user_id == g.user['id']).values(**values))
            if not result.rowcount:
                abort(404, 'Transaction not found')
        return {'ok': True}

    @app.delete('/api/transactions/<int:identity>')
    @auth
    def remove(identity):
        with engine.begin() as conn:
            result = conn.execute(delete(transactions).where(transactions.c.id == identity, transactions.c.user_id == g.user['id']))
            if not result.rowcount:
                abort(404, 'Transaction not found')
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
        return {'ok': True}

    @app.get('/api/export')
    @auth
    def export():
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(['Date', 'Type', 'Amount', 'Currency', 'Category', 'Account', 'Note'])
        with engine.connect() as conn:
            for r in conn.execute(select(transactions).where(transactions.c.user_id == g.user['id']).order_by(transactions.c.day)).mappings():
                note = r['note']
                if note.lstrip().startswith(('=', '+', '-', '@')) or note.startswith(('\t', '\r', '\n')):
                    note = "'" + note
                writer.writerow([r['day'], r['kind'], str(Decimal(r['amount']) / (100 if r['currency'] == 'USD' else 1)), r['currency'], r['category'], r['account'], note])
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
            if not changed:
                telegram('answerCallbackQuery', {'callback_query_id': callback_id, 'text': 'Already handled or unavailable'})
                return {'ok': True}
            telegram('answerCallbackQuery', {'callback_query_id': callback_id, 'text': status.capitalize()})
            delivered = telegram('sendMessage', {'chat_id': row['user_id'], 'text':
                '✅ បានអនុញ្ញាត / Access approved! Send /start and reopen MyMoney.' if status == 'approved'
                else '❌ សំណើត្រូវបានបដិសេធ / Access request rejected.'})
            telegram('editMessageText', {'chat_id': admin, 'message_id': message['message_id'],
                'text': f"{status.upper()} — {row['name']}\nTelegram ID: {row['user_id']}" +
                ('' if delivered else '\nNotification failed; access decision is saved.'),
                'reply_markup': {'inline_keyboard': []}})
            return {'ok': True}

        message = body.get('message', {})
        chat = message.get('chat', {})
        if chat.get('type') != 'private':
            return {'ok': True}
        user = message.get('from', {})
        uid = user.get('id')
        command = message.get('text', '').split(' ')[0].split('@')[0]
        payload = {'chat_id': chat['id']}
        if command == '/id':
            payload['text'] = f'Telegram ID: {uid}'
        elif command == '/request':
            payload['text'] = request_access(user)
        elif command == '/requests':
            if not admin or uid != admin:
                payload['text'] = '🔒 Admin only.'
            else:
                with engine.connect() as conn:
                    pending = conn.execute(select(access_requests).where(
                        access_requests.c.status == 'pending').order_by(access_requests.c.user_id).limit(5)).mappings().all()
                delivered = sum(bool(notify_admin(row)) for row in pending)
                payload['text'] = f'Pending requests sent: {delivered}/{len(pending)}. Approve/reject these, then send /requests for the next batch.' if pending else '✅ No pending requests.'
        elif not has_access(uid):
            payload['text'] = f'🔒 សូមស្នើសុំចូលប្រើ / Request access to MyMoney.\nTelegram ID: {uid}'
            payload['reply_markup'] = {'inline_keyboard': [[{
                'text': '🔓 ស្នើសុំចូលប្រើ / Request access', 'callback_data': 'request_access'}]]}
        else:
            payload['text'] = '💰 លុយខ្ញុំ · MyMoney\nកត់ចំណាយ និងមើលថវិការបស់អ្នក។\nOpen your personal money tracker below.'
            if uid == admin:
                payload['text'] += '\nAdmin: /requests — view pending access requests.'
            payload['reply_markup'] = {'inline_keyboard': [[{'text': '💰 បើក / Open MyMoney', 'web_app': {'url': app.config['APP_URL']}}]]}
        if not telegram('sendMessage', payload):
            return {'error': 'Telegram delivery failed'}, 502
        return {'ok': True}

    return app
