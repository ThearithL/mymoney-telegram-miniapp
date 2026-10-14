import hashlib
import hmac
import json
import time
from datetime import date
from urllib.parse import urlencode

import pytest
from sqlalchemy import insert, select, update

from app import create_app, transactions, budgets, registered_users, personal_tables, admin_audit
from insights import budget_snapshot

OWNER = 1219084924
OTHER = 987654321
TOKEN = '12345:test-token'


def headers(uid=OWNER, name='Bou'):
    data = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': uid, 'first_name': name})}
    key = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    data['hash'] = hmac.new(key, '\n'.join(f'{k}={v}' for k, v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
    return {'Authorization': 'tma ' + urlencode(data)}


@pytest.fixture
def project(tmp_path, monkeypatch):
    calls = []
    class Reply:
        ok = True
        def json(self): return {'ok': True}
    def post(url, json, **kwargs):
        calls.append((url.rsplit('/', 1)[-1], json))
        return Reply()
    monkeypatch.setattr('requests.post', post)
    config = {'TESTING': True, 'DATABASE_URL': 'sqlite:///' + str(tmp_path / 'test.db'),
              'BOT_TOKEN': TOKEN, 'ADMIN_USER_ID': str(OWNER), 'ALLOWED_USER_IDS': str(OTHER),
              'WEBHOOK_SECRET': 'testing-webhook-secret', 'APP_URL': 'https://example.test',
              'FLASK_SECRET_KEY': 'test-signing-key', 'ADMIN_PASSWORD': 'test-password'}
    app = create_app(config)
    yield app, app.test_client(), config, calls
    app.extensions['engine'].dispose()


def add_tx(conn, uid, amount, currency, day, kind='expense'):
    conn.execute(insert(transactions).values(user_id=uid, amount=amount, currency=currency, kind=kind,
        day=day, category='other', account='cash', note='', request_id=f'{uid}-{amount}-{day}-{kind}'))


def bot(client, command, uid=OWNER):
    return client.post('/telegram/webhook', headers={'X-Telegram-Bot-Api-Secret-Token':'testing-webhook-secret'},
        json={'message': {'chat': {'id': uid, 'type':'private'}, 'from': {'id':uid, 'first_name':'Bou'}, 'text':command}})


def test_existing_admin_rename_and_restart_preserve_records(project):
    app, client, config, calls = project
    engine = app.extensions['engine']
    with engine.begin() as conn:
        conn.execute(admin_audit.delete())  # Simulate database predating this update.
        conn.execute(update(personal_tables['profiles']).where(personal_tables['profiles'].c.user_id == OWNER).values(name='Bou', bio='Keep this biography'))
        add_tx(conn, OWNER, 7817, 'USD', date(2026, 10, 3))
        conn.execute(insert(budgets).values(user_id=OWNER, month='2026-10', currency='USD', amount=6000))
    upgraded = create_app(config)
    c = upgraded.test_client()
    assert c.get('/api/profile', headers=headers()).json['name'] == 'Thearith'
    assert c.get('/api/profile', headers=headers()).json['bio'] == 'Keep this biography'
    assert c.get('/api/data?month=2026-10', headers=headers()).json['user']['name'] == 'Thearith'
    assert bot(c, '/profile').status_code == 200
    assert '👤 Thearith' in calls[-1][1]['text']
    assert bot(c, '/name Thearith New').status_code == 200
    restarted = create_app(config)
    assert restarted.test_client().get('/api/profile', headers=headers()).json['name'] == 'Thearith New'
    with engine.connect() as conn:
        marker = conn.execute(select(admin_audit.c.action).where(admin_audit.c.target_id == OWNER)).scalar_one()
        assert len(marker) <= admin_audit.c.action.type.length
        assert conn.execute(select(transactions.c.amount)).scalar_one() == 7817
        assert conn.execute(select(budgets.c.amount)).scalar_one() == 6000
        assert conn.execute(select(personal_tables['profiles'].c.bio).where(personal_tables['profiles'].c.user_id == OWNER)).scalar_one() == 'Keep this biography'
    upgraded.extensions['engine'].dispose(); restarted.extensions['engine'].dispose()


def test_month_currency_isolation_and_over_budget(project):
    app, client, _, _ = project
    engine = app.extensions['engine']
    with engine.begin() as conn:
        add_tx(conn, OWNER, 7817, 'USD', date(2026,10,3))
        add_tx(conn, OWNER, 36050, 'KHR', date(2026,10,4))
        add_tx(conn, OWNER, 10000, 'USD', date(2026,10,4), 'income')
        add_tx(conn, OWNER, 1000, 'USD', date(2026,9,30))
        add_tx(conn, OTHER, 999999, 'USD', date(2026,10,4))
        for currency, amount in [('USD',6000),('KHR',500000)]:
            conn.execute(insert(budgets).values(user_id=OWNER, month='2026-10', currency=currency, amount=amount))
    data = budget_snapshot(engine, transactions, budgets, OWNER, '2026-10', date(2026,10,14))
    khr, usd = data['currencies']
    assert data['days_left'] == 18
    assert (usd['expense'], usd['remaining'], usd['used_percent'], usd['overspent'], usd['daily_allowance']) == (7817,-1817,'130.28',1817,0)
    assert usd['previous_month_expense'] == 1000 and usd['net'] == 2183
    assert (khr['remaining'], khr['used_percent'], khr['daily_allowance']) == (463950,'7.21',25775)
    api_data = client.get('/api/budget-status?month=2026-10&user_id=987654321', headers=headers()).json
    assert api_data['currencies'][1]['expense'] == 7817
    assert client.get('/api/budget-status?month=2026-10', headers=headers(OTHER)).json['currencies'][1]['expense'] == 999999


@pytest.mark.parametrize('limit,expense,status,percent', [(None,0,'unset',None),(0,0,'reached',None),(0,1,'over',None),(100,80,'warning','80.00'),(100,100,'reached','100.00')])
def test_budget_boundaries(project, limit, expense, status, percent):
    app, _, _, _ = project
    engine=app.extensions['engine']
    with engine.begin() as conn:
        if limit is not None:
            conn.execute(insert(budgets).values(user_id=OWNER,month='2026-02',currency='USD',amount=limit))
        if expense:
            add_tx(conn,OWNER,expense,'USD',date(2026,2,28))
    row=budget_snapshot(engine,transactions,budgets,OWNER,'2026-02',date(2026,2,28))['currencies'][1]
    assert row['status']==status and row['used_percent']==percent
    old=budget_snapshot(engine,transactions,budgets,OWNER,'2026-02',date(2026,3,1))
    assert old['days_left'] is None and old['currencies'][1]['daily_allowance'] is None


def test_profile_api_validation_and_isolation(project):
    app, client, _, _ = project
    assert client.put('/api/profile',headers=headers(),json={'name':'Thearith','bio':'Student'}).status_code==200
    assert client.put('/api/display-name',headers=headers(),json={'name':'New Name','user_id':OTHER}).status_code==200
    assert client.get('/api/profile',headers=headers()).json['bio']=='Student'
    assert client.get('/api/profile',headers=headers(OTHER,'Other')).json['name']==''
    for invalid in ['', ' '*3, 'x'*81, 'Name\nTest', None]:
        assert client.put('/api/display-name',headers=headers(),json={'name':invalid}).status_code==400
    assert client.get('/api/profile',headers=headers()).json['name']=='New Name'
    assert client.get('/api/budget-status').status_code==401
    assert client.put('/api/display-name',json={'name':'Intruder'}).status_code==401
    assert client.get('/api/budget-status',headers=headers(333)).status_code==403
    assert client.get('/api/budget-status?month=bad',headers=headers()).status_code==400
    assert client.post('/telegram/webhook',json={}).status_code==403


def test_bot_menu_admin_name_and_access(project):
    app, client, _, calls = project
    assert bot(client,'/menu').status_code==200
    rows=next(payload['reply_markup']['keyboard'] for _, payload in calls if 'keyboard' in payload.get('reply_markup', {}))
    texts=[button['text'] for row in rows for button in row]
    assert texts.count('✕ បិទ Menu / Close menu')==1
    assert '👤 Profile' in texts
    assert bot(client,'/budgetstatus').status_code==200
    assert 'No budget set' in calls[-1][1]['text']
    assert calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url'].endswith('/insights')
    assert bot(client,'/name').status_code==200
    assert 'Use:' in calls[-1][1]['text']
    assert bot(client,'/name Hacked',333).status_code==200
    assert 'Access disabled' in calls[-1][1]['text']
    callback={'callback_query':{'id':'1','from':{'id':OWNER,'first_name':'Bou'},'data':f'admin:user:{OWNER}',
                'message':{'chat':{'id':OWNER,'type':'private'}}}}
    assert client.post('/telegram/webhook',json=callback,headers={'X-Telegram-Bot-Api-Secret-Token':'testing-webhook-secret'}).status_code==200
    assert '👤 Thearith' in calls[-1][1]['text']
    assert bot(client,'/name ថារិទ្ធ').status_code==200
    assert client.get('/api/profile',headers=headers()).json['name']=='ថារិទ្ធ'


def test_new_page_assets_and_security_headers(project):
    _, client, _, _ = project
    for path in ['/insights','/insights-assets/app.js','/insights-assets/style.css']:
        result=client.get(path)
        assert result.status_code==200
        assert "default-src 'self'" in result.headers['Content-Security-Policy']
    assert client.get('/insights-assets/../../app.py').status_code==404
