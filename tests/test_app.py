import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
import pytest
from app import create_app

TOKEN = '123456:test-token'
ADMIN_TEST_PASSWORD = 'TestAdminPassword-2026!'

def unlock_admin(client,uid=123,password=ADMIN_TEST_PASSWORD):
    return client.post('/api/admin/unlock',headers=headers(uid=uid),json={'password':password})

def headers(uid=123, age=0, tamper=False):
    data = {'auth_date': str(int(time.time())-age), 'user': json.dumps({'id': uid, 'first_name': 'Test'})}
    secret = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    data['hash'] = hmac.new(secret, '\n'.join(f'{k}={v}' for k,v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
    if tamper:
        data['user'] = json.dumps({'id': 456})
    return {'Authorization': 'tma '+urlencode(data)}

@pytest.fixture
def client(tmp_path):
    app = create_app({'TESTING': True, 'BOT_TOKEN': TOKEN, 'ALLOWED_USER_IDS': '123,456',
        'DATABASE_URL': 'sqlite:///'+str(tmp_path/'test.db'), 'WEBHOOK_SECRET': 'secret'})
    return app.test_client()

def payload(**overrides):
    return dict(kind='expense',amount='12.34',currency='USD',category='food',account='cash',
        note='Lunch',day='2026-01-02',request_id='unique-request-123',**overrides)

def test_auth_rejects_missing_tampered_expired_and_unlisted(client):
    assert client.get('/api/data').status_code == 401
    assert client.get('/api/data', headers=headers(tamper=True)).status_code == 401
    assert client.get('/api/data', headers=headers(age=3601)).status_code == 401
    assert client.get('/api/data', headers=headers(uid=999)).status_code == 403
    assert client.get('/api/data', headers=headers(age=-100)).status_code == 401

def test_crud_idempotency_and_ownership(client):
    data=payload()
    a=client.post('/api/transactions',json=data,headers=headers())
    assert a.status_code == 201
    identity=a.json['id']
    assert client.post('/api/transactions',json=data,headers=headers()).json['id']==identity
    rows=client.get('/api/data?month=2026-01',headers=headers()).json['transactions']
    assert len(rows)==1 and rows[0]['amount']==1234
    assert not client.get('/api/data?month=2026-01',headers=headers(uid=456)).json['transactions']
    data['amount']='20'
    assert client.put(f'/api/transactions/{identity}',json=data,headers=headers(uid=456)).status_code==404
    assert client.delete(f'/api/transactions/{identity}',headers=headers(uid=456)).status_code==404
    assert client.put(f'/api/transactions/{identity}',json=data,headers=headers()).status_code==200
    assert client.get('/api/data?month=2026-01',headers=headers()).json['transactions'][0]['amount']==2000
    assert client.delete(f'/api/transactions/{identity}',headers=headers()).status_code==200
    assert not client.get('/api/data?month=2026-01',headers=headers()).json['transactions']

def test_personal_record_qr_is_authenticated_and_owner_scoped(client,monkeypatch):
    # The runtime dependency is installed from requirements.txt in deployment.
    # Stub its encoder here so this test remains offline-friendly.
    import sys,types
    from PIL import Image
    monkeypatch.setitem(sys.modules,'qrcode',types.SimpleNamespace(make=lambda _payload:Image.new('RGB',(21,21),'black')))
    created=client.post('/api/transactions',json=payload(),headers=headers())
    identity=created.json['id']
    assert client.get(f'/api/transactions/{identity}/qr').status_code==401
    assert client.get(f'/api/transactions/{identity}/qr',headers=headers(uid=456)).status_code==404
    response=client.get(f'/api/transactions/{identity}/qr',headers=headers())
    assert response.status_code==200
    assert response.mimetype=='image/png'
    assert response.data.startswith(b'\x89PNG\r\n\x1a\n')
    assert response.headers['Cache-Control']=='no-store'

@pytest.mark.parametrize('amount,currency', [('0','USD'),('-1','KHR'),('1.001','USD'),('1.1','KHR'),('NaN','USD'),('Infinity','USD'),('100','EUR')])
def test_rejects_invalid_money(client,amount,currency):
    data=payload();data.update(amount=amount,currency=currency)
    assert client.post('/api/transactions',json=data,headers=headers()).status_code==400

@pytest.mark.parametrize('kind,category', [('expense','salary'),('income','food')])
def test_transaction_category_must_match_kind(client,kind,category):
    data=payload();data.update(kind=kind,category=category)
    assert client.post('/api/transactions',json=data,headers=headers()).status_code==400
    valid={**data,'category':'other','request_id':'valid-category-'+kind}
    assert client.post('/api/transactions',json=valid,headers=headers()).status_code==201

def test_budget_currency_and_month_isolation(client):
    for currency,amount in [('USD','100.25'),('KHR','200000')]:
        response=client.put('/api/budget',json={'month':'2026-01','currency':currency,'amount':amount},headers=headers())
        assert response.status_code==200
        assert response.json['amount']==(10025 if currency=='USD' else 200000)
    updated=client.put('/api/budget',json={'month':'2026-01','currency':'USD','amount':'137'},headers=headers())
    assert updated.json=={'ok':True,'month':'2026-01','currency':'USD','amount':13700}
    budgets=client.get('/api/data?month=2026-01',headers=headers()).json['budgets']
    assert {b['currency']:b['amount'] for b in budgets}=={'USD':13700,'KHR':200000}
    assert not client.get('/api/data?month=2026-02',headers=headers()).json['budgets']
    assert not client.get('/api/data?month=2026-01',headers=headers(uid=456)).json['budgets']

@pytest.mark.parametrize('currency,amount', [('KHR','0'),('USD','0'),('USD','0.00')])
def test_monthly_budget_accepts_zero(client,currency,amount):
    response=client.put('/api/budget',json={'month':'2026-10','currency':currency,'amount':amount},headers=headers())
    assert response.status_code==200
    assert response.json['amount']==0
    saved=client.get('/api/data?month=2026-10',headers=headers()).json['budgets']
    assert any(row['currency']==currency and row['amount']==0 for row in saved)

def test_monthly_budget_limit_can_be_edited_to_zero_and_back(client):
    url='/api/budget'
    save=lambda amount,currency='USD',month='2026-10': client.put(url,
        json={'month':month,'currency':currency,'amount':amount},headers=headers())
    assert save('137.00').json['amount']==13700
    assert save('0').json=={'ok':True,'month':'2026-10','currency':'USD','amount':0}
    # Editing uses the same month/currency row; it must not create duplicate budgets.
    assert save('24.50').json['amount']==2450
    saved=client.get('/api/data?month=2026-10',headers=headers()).json['budgets']
    usd_rows=[row for row in saved if row['currency']=='USD']
    assert len(usd_rows)==1 and usd_rows[0]['amount']==2450
    assert save('0','KHR').json['amount']==0
    assert save('10','USD','2026-11').json['amount']==1000
    october=client.get('/api/data?month=2026-10',headers=headers()).json['budgets']
    assert {row['currency']:row['amount'] for row in october}=={'USD':2450,'KHR':0}
    assert client.get('/api/data?month=2026-11',headers=headers()).json['budgets'][0]['amount']==1000

@pytest.mark.parametrize('currency,amount', [('USD','-1'),('USD','0.001'),('KHR','1.1'),('USD','NaN')])
def test_monthly_budget_rejects_invalid_amount_without_changing_saved_limit(client,currency,amount):
    client.put('/api/budget',json={'month':'2026-10','currency':'USD','amount':'50'},headers=headers())
    response=client.put('/api/budget',json={'month':'2026-10','currency':currency,'amount':amount},headers=headers())
    assert response.status_code==400
    budgets=client.get('/api/data?month=2026-10',headers=headers()).json['budgets']
    assert {row['currency']:row['amount'] for row in budgets}=={'USD':5000}

def test_zero_budget_does_not_trigger_division_or_false_alert(client,monkeypatch):
    calls=[]
    monkeypatch.setattr('app.requests.post',lambda *a,**k:calls.append((a,k)))
    response=client.put('/api/budget',json={'month':__import__('datetime').date.today().strftime('%Y-%m'),'currency':'USD','amount':'0'},headers=headers())
    assert response.status_code==200
    assert calls==[]

def test_owner_can_add_and_remove_admin_in_mini_app(access_client):
    client,calls,_=access_client
    added=client.post('/api/admin/admins',headers=headers(),json={'user_id':456,'confirm':True})
    assert added.status_code==201
    assert added.json['user_id']==456
    assert client.get('/api/admin/users',headers=headers()).json['users'][0]['status']=='admin'
    assert client.get('/api/admin/users/456',headers=headers()).status_code==200
    assert unlock_admin(client,456).status_code==200
    assert client.get('/api/admin/users',headers=headers(uid=456)).status_code==200
    # A promoted admin must see the bot menu entry and be directed to the Mini App console.
    calls.clear()
    assert message(client,456,'/start').status_code==200
    menu_messages=[p for _,p in calls if 'keyboard' in p.get('reply_markup',{})]
    assert any('🛡 Admin' in str(p['reply_markup']['keyboard']) for p in menu_messages)
    assert not any('⏳ Requests' in str(p['reply_markup']['keyboard']) for p in menu_messages)
    assert calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url']=='https://example.com'
    calls.clear()
    assert message(client,456,'/admin').status_code==200
    assert calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url']=='https://example.com'
    calls.clear()
    assert callback(client,456,'admin:stats').status_code==200
    assert calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url']=='https://example.com'
    assert client.post('/api/admin/admins',headers=headers(uid=456),json={'user_id':789,'confirm':True}).status_code==403
    removed=client.delete('/api/admin/admins/456',headers=headers())
    assert removed.status_code==200
    data=client.get('/api/data?month=2026-01',headers=headers(uid=456))
    assert data.status_code==200 and data.json['user']['is_admin'] is False
    calls.clear()
    message(client,456,'/start')
    assert not any('🛡 Admin' in str(p.get('reply_markup',{})) for _,p in calls)

def test_regular_user_cannot_manage_admins(access_client):
    client,_,_ = access_client
    assert client.get('/api/admin/admins',headers=headers(uid=456)).status_code==403
    assert client.put('/api/admin/users/456/access',headers=headers(uid=456),
        json={'status':'approved','confirm':True}).status_code==403

def test_admin_dashboard_and_owner_transaction_crud_and_messaging(access_client):
    client,calls,_=access_client
    from app import personal_tables, registered_users, insert, select, func
    # A registered user can be messaged even before recording any transactions.
    with client.application.extensions['engine'].begin() as conn:
        conn.execute(insert(registered_users).values(user_id=456,name='Test user',last_seen=1))
    dashboard=client.get('/api/admin/overview',headers=headers())
    assert dashboard.status_code==200
    assert dashboard.json['user_count']>=2
    assert set(dashboard.json['statuses'])=={'admin','approved','pending','revoked','deleted','not_requested'}
    assert client.get('/api/admin/overview',headers=headers(uid=456)).status_code==403

    body=payload(request_id='admin-created-record',day=__import__('datetime').date.today().isoformat())
    created=client.post('/api/admin/users/456/transactions',headers=headers(),json=body)
    assert created.status_code==201
    identity=created.json['id']
    changed={**body,'amount':'30.00','note':'Admin corrected record'}
    assert client.put(f'/api/admin/users/456/transactions/{identity}',headers=headers(),json=changed).status_code==200
    assert client.delete(f'/api/admin/users/456/transactions/{identity}',headers=headers()).json['recoverable'] is True
    engine=client.application.extensions['engine']
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(personal_tables['trash']).where(
            personal_tables['trash'].c.user_id==456)).scalar()==1

    sent=client.post('/api/admin/users/456/message',headers=headers(),json={'text':'Hello from MyMoney admin'})
    assert sent.status_code==200 and sent.json['delivered'] is True
    assert calls[-1][1]['chat_id']==456 and calls[-1][1]['text']=='Hello from MyMoney admin'
    history=client.get('/api/admin/users/456/messages',headers=headers())
    assert history.status_code==200 and history.json['messages'][0]['text']=='Hello from MyMoney admin'
    assert client.post('/api/admin/users/456/message',headers=headers(),json={'text':' '}).status_code==400
    assert client.post('/api/admin/admins',headers=headers(),json={'user_id':456,'confirm':True}).status_code==201
    assert unlock_admin(client,456).status_code==200
    assert client.post('/api/admin/users/456/message',headers=headers(uid=456),json={'text':'Not owner'}).status_code==403
    assert client.delete(f'/api/admin/users/456/transactions/{identity}',headers=headers(uid=456)).status_code==403

def test_owner_can_create_filter_and_permanently_remove_user_with_exact_id_confirmation(access_client):
    client,calls,_=access_client
    created=client.post('/api/admin/users',headers=headers(),json={'user_id':789,'name':'New personal user'})
    assert created.status_code==201 and created.json['status']=='approved'
    assert calls[-1][1]['chat_id']==789
    detail=client.get('/api/admin/users/789',headers=headers())
    assert detail.status_code==200 and detail.json['user']['name']=='New personal user'
    renamed=client.put('/api/admin/users/789',headers=headers(),json={'name':'Updated display label'})
    assert renamed.status_code==200 and client.get('/api/admin/users/789',headers=headers()).json['user']['name']=='Updated display label'
    assert client.post('/api/admin/users',headers=headers(),json={'user_id':789}).status_code==409
    assert client.post('/api/admin/users/789/transactions',headers=headers(),json=payload(request_id='created-for-removal')).status_code==201
    assert client.delete('/api/admin/users/789',headers=headers(),json={'confirm_id':'123'}).status_code==400
    assert client.delete('/api/admin/users/123',headers=headers(),json={'confirm_id':'123'}).status_code==400
    assert client.delete('/api/admin/users/789',headers=headers(),json={'confirm_id':'789'}).json=={
        'ok':True,'deleted_user_id':789}
    assert client.get('/api/admin/users/789',headers=headers()).status_code==404
    assert client.get('/api/admin/users/789/messages',headers=headers()).status_code==404
    assert client.get('/api/data',headers=headers(uid=789)).status_code==403
    from app import registered_users, access_requests, transactions, deleted_users, admin_audit, select
    with client.application.extensions['engine'].connect() as conn:
        assert conn.execute(select(registered_users.c.user_id).where(registered_users.c.user_id==789)).first() is None
        assert conn.execute(select(access_requests.c.user_id).where(access_requests.c.user_id==789)).first() is None
        assert conn.execute(select(transactions.c.id).where(transactions.c.user_id==789)).first() is None
        assert conn.execute(select(deleted_users.c.user_hash)).first() is not None
        assert conn.execute(select(admin_audit.c.target_id).where(admin_audit.c.target_id==789)).first() is None
    assert client.delete('/api/admin/users/789',headers=headers(),json={'confirm_id':'789'}).status_code==404
    assert message(client,789,'/request').status_code==200 and 'account was removed' in calls[-1][1]['text']
    # An additional admin can view users but cannot create or delete them.
    assert client.post('/api/admin/admins',headers=headers(),json={'user_id':456,'confirm':True}).status_code==201
    assert client.post('/api/admin/users',headers=headers(uid=456),json={'user_id':790}).status_code==403
    assert client.delete('/api/admin/users/456',headers=headers(uid=456),json={'confirm_id':'456'}).status_code==403

def test_deleted_user_stays_blocked_even_if_legacy_allowlisted(tmp_path):
    from werkzeug.security import generate_password_hash
    client=create_app({'TESTING':True,'BOT_TOKEN':TOKEN,'ADMIN_USER_ID':'123','ALLOWED_USER_IDS':'789',
        'ADMIN_PASSWORD_HASH':generate_password_hash(ADMIN_TEST_PASSWORD),
        'DATABASE_URL':'sqlite:///'+str(tmp_path/'deleted-allowlist.db')}).test_client()
    assert unlock_admin(client).status_code==200
    assert client.get('/api/data',headers=headers(uid=789)).status_code==200
    removed=client.delete('/api/admin/users/789',headers=headers(),json={'confirm_id':'789'})
    assert removed.status_code==200
    assert client.get('/api/data',headers=headers(uid=789)).status_code==403

def test_admin_dashboard_requires_password_and_can_be_locked(access_client):
    client,_,_=access_client
    assert client.get('/api/admin/overview',headers=headers()).status_code==200
    assert client.post('/api/admin/lock',headers=headers()).status_code==200
    assert client.get('/api/admin/overview',headers=headers()).status_code==401
    assert client.post('/api/admin/unlock',headers=headers(),json={'password':'wrong'}).status_code==401
    assert client.post('/api/admin/unlock',headers=headers(),json={'password':ADMIN_TEST_PASSWORD}).status_code==200
    assert client.get('/api/admin/overview',headers=headers()).status_code==200

def test_admin_password_lockout_after_five_failures(access_client):
    client,_,_=access_client
    assert client.post('/api/admin/lock',headers=headers()).status_code==200
    for _ in range(4):
        assert client.post('/api/admin/unlock',headers=headers(),json={'password':'incorrect'}).status_code==401
    assert client.post('/api/admin/unlock',headers=headers(),json={'password':'incorrect'}).status_code==429
    assert client.post('/api/admin/unlock',headers=headers(),json={'password':ADMIN_TEST_PASSWORD}).status_code==429

def test_admin_can_add_pending_user_by_seen_telegram_username(access_client):
    client,_,_=access_client
    from app import access_requests, registered_users, insert
    with client.application.extensions['engine'].begin() as conn:
        conn.execute(insert(registered_users).values(user_id=987654,name='Tester',username='testuser',last_seen=1))
        conn.execute(insert(access_requests).values(user_id=987654,name='Tester',username='testuser',
            status='pending',request_key='pending-testuser',notified_at=0))
    created=client.post('/api/admin/users',headers=headers(),json={'user_id':'@TestUser','name':'Test account'})
    assert created.status_code==201 and created.json['user_id']==987654
    missing=client.post('/api/admin/users',headers=headers(),json={'user_id':'@unknownuser'})
    assert missing.status_code==404 and 'send /start or /request' in missing.json['error']

def test_recent_activity_button_and_command_are_private_and_show_latest_five(access_client):
    client,calls,_=access_client
    for uid, note, amount in [(123, f'Owner record {i}', str(i + 1)) for i in range(6)]:
        record=payload(note=note,amount=amount,day='2026-10-05',request_id=f'owner-recent-{i}')
        assert client.post('/api/transactions',headers=headers(uid=uid),json=record).status_code==201
    from app import insert, transactions
    with client.application.extensions['engine'].begin() as conn:
        conn.execute(insert(transactions).values(user_id=456,kind='expense',amount=1000,
            currency='USD',category='food',spending_type='essential',account='cash',
            note='Other user secret',day='2026-10-05',request_id='other-recent'))

    assert message(client,123,'/start').status_code==200
    keyboards=[p['reply_markup']['keyboard'] for _,p in calls if 'keyboard' in p.get('reply_markup',{})]
    assert any('🕘 ប្រតិបត្តិការថ្មីៗ / Recent activity' in str(rows) for rows in keyboards)
    calls.clear()
    assert message(client,123,'/recent').status_code==200
    recent=[p['text'] for _,p in calls if p.get('text','').startswith('🕘 Recent activity')]
    assert len(recent)==1
    assert 'Owner record 5' in recent[0] and 'Owner record 1' in recent[0]
    assert 'Owner record 0' not in recent[0] and 'Other user secret' not in recent[0]
    calls.clear()
    assert callback(client,123,'recent').status_code==200
    assert any(p.get('text','').startswith('🕘 Recent activity') for _,p in calls)

def test_expense_need_want_and_yearly_summary(client):
    essential=payload(request_id='essential-123',amount='25',spending_type='essential')
    wanted=payload(request_id='want-entry-123',amount='10',category='coffee',spending_type='want',day='2026-02-03')
    income=payload(request_id='income-entry-123',kind='income',category='salary',amount='200',spending_type=None,day='2026-02-04')
    assert client.post('/api/transactions',json=essential,headers=headers()).status_code==201
    assert client.post('/api/transactions',json=wanted,headers=headers()).status_code==201
    assert client.post('/api/transactions',json=income,headers=headers()).status_code==201
    data=client.get('/api/yearly-summary?year=2026',headers=headers()).json
    assert data['year']==2026
    assert {row['type']:row['amount'] for row in data['spending_types']}=={'essential':2500,'want':1000}
    assert {row['kind']:row['amount'] for row in data['totals']}=={'expense':3500,'income':20000}
    assert {row['month']:row['amount'] for row in data['monthly'] if row['kind']=='expense'}=={'2026-01':2500,'2026-02':1000}
    assert client.get('/api/yearly-summary?year=1999',headers=headers()).status_code==400

def test_reject_invalid_expense_spending_type(client):
    data=payload(spending_type='sometimes')
    assert client.post('/api/transactions',json=data,headers=headers()).status_code==400
    data['request_id']='unclassified-entry-123'
    data['spending_type']='none'
    assert client.post('/api/transactions',json=data,headers=headers()).status_code==201
    record=client.get('/api/data?month=2026-01',headers=headers()).json['transactions'][0]
    assert record['spending_type']=='none'

def test_monthly_needs_and_wants_limits_update_and_are_private(client):
    endpoint='/api/spending-budgets'
    body={'month':'2026-01','currency':'USD','spending_type':'essential','amount':'80'}
    assert client.put(endpoint,json=body,headers=headers()).json=={
        'ok':True,'month':'2026-01','currency':'USD','spending_type':'essential','amount':8000}
    body['amount']='95.50'
    assert client.put(endpoint,json=body,headers=headers()).json['amount']==9550
    data=client.get('/api/data?month=2026-01',headers=headers()).json
    assert data['spending_budgets'][0]['amount']==9550
    assert client.get('/api/data?month=2026-01',headers=headers(uid=456)).json['spending_budgets']==[]
    assert client.delete(endpoint,json={'month':'2026-01','currency':'USD','spending_type':'essential'},headers=headers()).status_code==200
    assert client.get('/api/data?month=2026-01',headers=headers()).json['spending_budgets']==[]
    assert client.put(endpoint,json={**body,'spending_type':'other'},headers=headers()).status_code==400

def test_csv_formula_safety_and_ownership(client):
    data=payload();data['note']='=HYPERLINK("evil")'
    client.post('/api/transactions',json=data,headers=headers())
    output=client.get('/api/export',headers=headers()).data.decode('utf-8-sig')
    assert "'=HYPERLINK" in output and '12.34' in output
    assert 'HYPERLINK' not in client.get('/api/export',headers=headers(uid=456)).data.decode()

def test_webhook_rejects_forgery_and_ignores_groups(client):
    assert client.post('/telegram/webhook',json={}).status_code==403
    assert client.post('/telegram/webhook',json={'message':{'chat':{'type':'group'}}},headers={'X-Telegram-Bot-Api-Secret-Token':'secret'}).status_code==200

def test_static_and_bad_input(client):
    assert client.get('/').status_code==200
    assert client.get('/health').json['ok']
    assert client.get('/api/data?month=oops',headers=headers()).status_code==400
    assert client.post('/api/transactions',json=[],headers=headers()).status_code==400

def test_admin_can_use_direct_render_password(tmp_path):
    chosen_password = 'Thearith-Admin-Test-2026!'
    client = create_app({'TESTING': True, 'BOT_TOKEN': TOKEN, 'ADMIN_USER_ID': '123',
        'ADMIN_PASSWORD': chosen_password,
        'DATABASE_URL': 'sqlite:///'+str(tmp_path/'direct-admin-password.db')}).test_client()
    security = client.get('/api/admin/security', headers=headers())
    assert security.status_code == 200 and security.json['password_configured'] is True
    assert client.post('/api/admin/unlock', headers=headers(), json={'password':'wrong'}).status_code == 401
    assert client.post('/api/admin/unlock', headers=headers(), json={'password':chosen_password}).status_code == 200

@pytest.fixture
def access_client(tmp_path, monkeypatch):
    calls = []
    class Result:
        ok = True
        def json(self):
            return {'ok': True, 'result': True}
    def post(url, json, timeout):
        calls.append((url.rsplit('/',1)[-1], json))
        return Result()
    monkeypatch.setattr('app.requests.post', post)
    from werkzeug.security import generate_password_hash
    config = {'TESTING': True, 'BOT_TOKEN': TOKEN, 'ALLOWED_USER_IDS': '', 'ADMIN_USER_ID': '123',
        'ADMIN_PASSWORD_HASH': generate_password_hash(ADMIN_TEST_PASSWORD),
        'DATABASE_URL': 'sqlite:///'+str(tmp_path/'access.db'), 'WEBHOOK_SECRET': 'secret', 'APP_URL':'https://example.com'}
    client=create_app(config).test_client()
    assert unlock_admin(client).status_code==200
    return client, calls, config

def message(client, uid, text):
    return client.post('/telegram/webhook', headers={'X-Telegram-Bot-Api-Secret-Token':'secret'},
        json={'message':{'chat':{'id':uid,'type':'private'}, 'from':{'id':uid,'first_name':'User'},'text':text}})

def callback(client, uid, data):
    return client.post('/telegram/webhook', headers={'X-Telegram-Bot-Api-Secret-Token':'secret'},
        json={'callback_query':{'id':'callback1','from':{'id':uid,'first_name':'User'},'data':data,
            'message':{'message_id':1,'chat':{'id':uid,'type':'private'}}}})

def pending_key(client):
    from app import access_requests, select
    with client.application.extensions['engine'].connect() as conn:
        return conn.execute(select(access_requests.c.request_key)).scalar_one()

def test_request_approval_persistence_and_isolation(access_client):
    client,calls,config=access_client
    assert client.get('/api/data',headers=headers()).status_code==200  # admin automatically allowed
    assert client.get('/api/data',headers=headers(uid=456)).status_code==403
    assert message(client,456,'/start').status_code==200
    assert calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['callback_data']=='request_access'
    assert callback(client,456,'request_access').status_code==200
    key=pending_key(client)
    assert any(p.get('chat_id')==123 and 'reply_markup' in p for _,p in calls)
    assert callback(client,123,'approve:'+key).status_code==200
    assert client.get('/api/data',headers=headers(uid=456)).status_code==200
    assert message(client,456,'/start').status_code==200
    assert calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url']=='https://example.com'
    assert client.post('/api/transactions',headers=headers(uid=456),json=payload()).status_code==201
    assert not client.get('/api/data?month=2026-01',headers=headers()).json['transactions']
    restarted=create_app(config).test_client()
    assert restarted.get('/api/data',headers=headers(uid=456)).status_code==200
    assert callback(client,123,'reject:'+key).status_code==200  # stale decision cannot reverse approval
    assert restarted.get('/api/data',headers=headers(uid=456)).status_code==200

def test_cannot_self_approve_or_access_admin_requests(access_client):
    client,calls,_=access_client
    message(client,456,'/request')
    key=pending_key(client)
    callback(client,456,'approve:'+key)
    assert client.get('/api/data',headers=headers(uid=456)).status_code==403
    message(client,456,'/requests')
    assert calls[-1][1]['text']=='🔒 Admin only.'
    callback(client,123,'reject:'+key)
    assert client.get('/api/data',headers=headers(uid=456)).status_code==403
    message(client,456,'/request')
    assert 'rejected' in calls[-1][1]['text']

def test_request_throttle_and_admin_recovery(access_client):
    client,calls,_=access_client
    message(client,456,'/request')
    message(client,456,'/request')
    notifications=[p for method,p in calls if method=='sendMessage' and p['chat_id']==123]
    assert len(notifications)==1
    message(client,123,'/requests')
    assert '1/1' in calls[-1][1]['text']

def test_id_available_before_admin_bootstrap(access_client):
    _,calls,config=access_client
    config['ADMIN_USER_ID']=''
    client=create_app(config).test_client()
    assert message(client,123,'/id').status_code==200
    assert calls[-1][1]['text']=='Telegram ID: 123'
    message(client,456,'/request')
    assert 'Admin not configured' in calls[-1][1]['text']
    assert client.get('/api/data',headers=headers()).status_code==503

def test_admin_menu_and_no_privilege_leak(access_client):
    client,calls,_=access_client
    message(client,123,'/start')
    menus=[p for _,p in calls if 'keyboard' in p.get('reply_markup',{})]
    assert any('🛡 Admin' in str(p) for p in menus)
    calls.clear()
    message(client,456,'/start')
    assert not any('🛡 Admin' in str(p) for _,p in calls)
    message(client,123,'/admin')
    assert 'Admin Control' in calls[-1][1]['text']
    callback(client,456,'admin:stats')
    assert calls[-1][1]['text']=='🔒 Admin only.'
    message(client,456,'/admin')
    assert calls[-1][1]['text']=='🔒 Admin only.'

def test_start_sends_english_welcome_and_usage_instructions(access_client):
    client,calls,_=access_client
    assert message(client,123,'/start').status_code==200
    welcome=calls[0][1]['text']
    assert 'Welcome to MyMoney!' in welcome
    assert 'How to get started:' in welcome
    assert 'Request access' in welcome and 'Monthly budget' in welcome
    assert 'owner/admin can review' in welcome
    assert 'Savings goals' in welcome and 'all personal features' in welcome
    assert calls[1][1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url']=='https://example.com'

    calls.clear()
    assert message(client,456,'/start').status_code==200
    restricted_welcome=calls[0][1]['text']
    assert 'Your account needs approval' in restricted_welcome
    assert 'all personal features' not in restricted_welcome
    assert calls[1][1]['reply_markup']['inline_keyboard'][0][0]['callback_data']=='request_access'
    calls.clear()
    assert message(client,456,'/help').status_code==200
    assert 'borrowed or lent money' in calls[-1][1]['text']

def test_admin_view_and_revoke_grant_with_single_use_confirmation(access_client):
    client,calls,_=access_client
    message(client,456,'/request')
    callback(client,123,'approve:'+pending_key(client))
    client.post('/api/transactions',headers=headers(uid=456),json=payload())
    callback(client,123,'admin:user:456')
    assert '12.34 USD' in calls[-1][1]['text']
    callback(client,123,'admin:tx:456:0')
    assert 'Lunch' in calls[-1][1]['text']
    callback(client,123,'admin:revoke:456')
    confirm=calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['callback_data']
    assert client.get('/api/data',headers=headers(uid=456)).status_code==200
    callback(client,456,confirm)
    assert client.get('/api/data',headers=headers(uid=456)).status_code==200
    callback(client,123,confirm)
    assert client.get('/api/data',headers=headers(uid=456)).status_code==403
    callback(client,123,confirm)
    assert 'already used' in calls[-1][1]['text']
    callback(client,123,'admin:grant:456')
    grant=calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['callback_data']
    callback(client,123,grant)
    rows=client.get('/api/data?month=2026-01',headers=headers(uid=456)).json['transactions']
    assert len(rows)==1  # revocation preserves financial data
    callback(client,123,'admin:audit:0')
    assert 'revoke' in calls[-1][1]['text'] and 'grant' in calls[-1][1]['text']
    callback(client,123,'admin:revoke:123')
    assert 'cannot be revoked' in calls[-1][1]['text']

def test_revoke_overrides_environment_allowlist(access_client):
    _,calls,config=access_client
    config['ALLOWED_USER_IDS']='456'
    client=create_app(config).test_client()
    assert client.get('/api/data',headers=headers(uid=456)).status_code==200
    callback(client,123,'admin:revoke:456')
    callback(client,123,calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['callback_data'])
    assert client.get('/api/data',headers=headers(uid=456)).status_code==403

def test_admin_confirmation_expiry_and_stale_replacement(access_client):
    from app import admin_actions, update
    client,calls,_=access_client
    message(client,456,'/request')
    callback(client,123,'admin:grant:456')
    first=calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['callback_data']
    callback(client,123,'admin:revoke:456')
    second=calls[-1][1]['reply_markup']['inline_keyboard'][0][0]['callback_data']
    callback(client,123,first)
    assert 'expired' in calls[-1][1]['text']
    with client.application.extensions['engine'].begin() as conn:
        conn.execute(update(admin_actions).values(expires_at=0))
    callback(client,123,second)
    assert 'expired' in calls[-1][1]['text']
    assert client.get('/api/data',headers=headers(uid=456)).status_code==403

def test_current_summary_and_personal_bot_summary(client, monkeypatch):
    from app import datetime, TZ
    day=datetime.now(TZ).date().isoformat()
    data=payload();data['day']=day
    client.post('/api/transactions',json=data,headers=headers())
    for period in ('today','week','month'):
        response=client.get('/api/summary?period='+period,headers=headers())
        assert response.status_code==200
        assert response.json['totals']==[{'currency':'USD','kind':'expense','amount':1234}]
        assert not client.get('/api/summary?period='+period,headers=headers(uid=456)).json['totals']
    assert client.get('/api/summary?period=bad',headers=headers()).status_code==400

def test_admin_status_does_not_expose_credentials(access_client):
    client,calls,_=access_client
    callback(client,123,'admin:system')
    text=calls[-1][1]['text']
    assert TOKEN not in text and 'sqlite:///' not in text and 'secret\n' not in text
    callback(client,123,'admin:users:0')
    assert 'All known users' in calls[-1][1]['text']
    callback(client,123,'admin:stats')
    assert 'Known users:' in calls[-1][1]['text']

def test_goals_ownership_precision_versions_and_idempotence(client):
    data={'title':'Laptop','currency':'USD','target':'800','saved':'100.25','request_id':'goal-request-123'}
    response=client.post('/api/goals',headers=headers(),json=data)
    assert response.status_code==201
    gid=response.json['id']
    assert client.post('/api/goals',headers=headers(),json=data).json['id']==gid
    goal=client.get('/api/goals',headers=headers()).json['goals'][0]
    assert goal['target']==80000 and goal['saved']==10025 and goal['version']==1
    assert not client.get('/api/goals',headers=headers(uid=456)).json['goals']
    data.update(version=1,saved='200')
    assert client.put(f'/api/goals/{gid}',headers=headers(uid=456),json=data).status_code==404
    assert client.delete(f'/api/goals/{gid}',headers=headers(uid=456)).status_code==404
    assert client.put(f'/api/goals/{gid}',headers=headers(),json=data).status_code==200
    assert client.put(f'/api/goals/{gid}',headers=headers(),json=data).status_code==409
    data.update(version=2,currency='KHR')
    assert client.put(f'/api/goals/{gid}',headers=headers(),json=data).status_code==400
    assert client.delete(f'/api/goals/{gid}',headers=headers()).status_code==200
    assert not client.get('/api/goals',headers=headers()).json['goals']
    assert not client.get('/api/data?month=2026-01',headers=headers()).json['transactions']

def test_goal_deposits_withdrawals_history_and_notifications(client,monkeypatch):
    calls=[]
    class Result:
        ok=True
        def json(self):return {'ok':True}
    monkeypatch.setattr('app.requests.post',lambda url,json,timeout:(calls.append(json) or Result()))
    created=client.post('/api/goals',headers=headers(),json={'title':'Laptop','currency':'USD',
        'target':'100','saved':'20','request_id':'goal-history-test'})
    goal_id=created.json['id']
    add={'direction':'add','amount':'40','request_id':'goal-deposit-123'}
    response=client.post(f'/api/goals/{goal_id}/entries',headers=headers(),json=add)
    assert response.status_code==200 and response.json['saved']==6000 and response.json['percent']==60
    assert client.post(f'/api/goals/{goal_id}/entries',headers=headers(),json=add).json['duplicate'] is True
    withdraw={'direction':'withdraw','amount':'10','request_id':'goal-withdraw-123'}
    assert client.post(f'/api/goals/{goal_id}/entries',headers=headers(),json=withdraw).json['saved']==5000
    assert client.post(f'/api/goals/{goal_id}/entries',headers=headers(),json={'direction':'withdraw',
        'amount':'51','request_id':'too-much-withdraw'}).status_code==400
    finish={'direction':'add','amount':'50','request_id':'goal-finish-123'}
    assert client.post(f'/api/goals/{goal_id}/entries',headers=headers(),json=finish).json['remaining']==0
    goal=client.get('/api/goals',headers=headers()).json['goals'][0]
    assert goal['saved']==10000 and goal['percent']==100 and goal['remaining']==0
    assert len(calls)==3 and '100%' in calls[-1]['text']
    entries=client.get(f'/api/goals/{goal_id}/entries',headers=headers()).json['entries']
    assert [row['direction'] for row in entries]==['add','withdraw','add','opening']
    assert client.get('/api/data?month=2026-01',headers=headers()).json['transactions']==[]
    assert client.get(f'/api/goals/{goal_id}/entries',headers=headers(uid=456)).status_code==404

def test_completed_goal_can_be_hidden_restored_and_deleted(client):
    created=client.post('/api/goals',headers=headers(),json={'title':'Phone','currency':'USD',
        'target':'100','saved':'100','request_id':'goal-archive-test'})
    goal_id=created.json['id']
    assert client.post(f'/api/goals/{goal_id}/archive',headers=headers(uid=456),json={'archived':True}).status_code==404
    assert client.post(f'/api/goals/{goal_id}/archive',headers=headers(),json={'archived':True}).json['archived'] is True
    assert client.get('/api/goals',headers=headers()).json['goals']==[]
    hidden=client.get('/api/goals?include_hidden=1',headers=headers()).json['goals']
    assert len(hidden)==1 and hidden[0]['archived']==1
    assert client.post(f'/api/goals/{goal_id}/archive',headers=headers(),json={'archived':False}).json['archived'] is False
    assert len(client.get('/api/goals',headers=headers()).json['goals'])==1
    assert client.delete(f'/api/goals/{goal_id}',headers=headers()).status_code==200
    assert client.get(f'/api/goals/{goal_id}/entries',headers=headers()).status_code==404

@pytest.mark.parametrize('field,value',[('saved','-1'),('saved','NaN'),('target','0'),('title',''),('saved','0.001')])
def test_invalid_goals(client,field,value):
    data={'title':'Laptop','currency':'USD','target':'800','saved':'0','request_id':'goal-invalid-123'}
    data[field]=value
    assert client.post('/api/goals',headers=headers(),json=data).status_code==400

def test_budget_alerts_once_per_threshold_and_no_other_user_leak(access_client):
    from app import datetime, TZ
    client,calls,_=access_client
    day=datetime.now(TZ).date().isoformat()
    client.put('/api/budget',headers=headers(),json={'month':day[:7],'currency':'USD','amount':'100'})
    data=payload();data.update(day=day,amount='80')
    response=client.post('/api/transactions',headers=headers(),json=data)
    assert response.status_code==201
    assert len(calls)==1 and calls[-1][1]['chat_id']==123 and '80%' in calls[-1][1]['text']
    client.post('/api/transactions',headers=headers(),json=data)
    assert len(calls)==1
    data.update(amount='21',request_id='next-expense-123')
    client.post('/api/transactions',headers=headers(),json=data)
    assert len(calls)==2 and 'exceeded' in calls[-1][1]['text']
    data.update(amount='1',request_id='third-expense-123')
    client.post('/api/transactions',headers=headers(),json=data)
    assert len(calls)==2

def test_telegram_daily_allowance_uses_budget_remaining(access_client):
    from app import datetime, TZ, display_money
    client,calls,_=access_client
    today=datetime.now(TZ).date()
    month=today.strftime('%Y-%m')
    client.put('/api/budget',headers=headers(),json={'month':month,'currency':'USD','amount':'100'})
    data=payload();data.update(day=today.isoformat(),amount='20')
    assert client.post('/api/transactions',headers=headers(),json=data).status_code==201

    response=message(client,123,'/allowance')
    assert response.status_code==200
    text=calls[-1][1]['text']
    days_left=(today.replace(day=28)+__import__('datetime').timedelta(days=4)).replace(day=1)
    remaining_days=(days_left-today).days
    assert 'Spendable today' in text
    assert f'Left: {display_money(8000,"USD")}' in text
    assert f'Daily amount: {display_money(8000//remaining_days,"USD")}' in text
    assert message(client,123,'/start').status_code==200
    keyboard=calls[-2][1]['reply_markup']['keyboard']
    assert any(row[0]['text']=='💸 ថ្ងៃនេះអាចចាយ / Daily allowance' for row in keyboard)

def test_budget_delivery_failure_keeps_transaction_and_retries(access_client,monkeypatch):
    from app import datetime, TZ
    import requests
    client,calls,_=access_client
    original=requests.post
    day=datetime.now(TZ).date().isoformat()
    client.put('/api/budget',headers=headers(),json={'month':day[:7],'currency':'USD','amount':'10'})
    def fail(*a,**kw):
        raise requests.Timeout()
    monkeypatch.setattr('app.requests.post',fail)
    data=payload();data.update(day=day,amount='9')
    assert client.post('/api/transactions',headers=headers(),json=data).status_code==201
    assert len(client.get('/api/data?month='+day[:7],headers=headers()).json['transactions'])==1
    monkeypatch.setattr('app.requests.post',original)
    assert client.post('/api/transactions',headers=headers(),json=data).status_code==201
    assert len(calls)==1

def test_summary_week_crosses_month_and_filters_users(client,monkeypatch):
    from datetime import datetime as real_datetime
    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls,tz=None):
            return cls(2026,10,1,12,tzinfo=tz)
    monkeypatch.setattr('app.datetime',FixedDateTime)
    data=payload();data.update(day='2026-09-30',amount='10')
    client.post('/api/transactions',headers=headers(),json=data)
    data.update(day='2026-10-01',amount='20',request_id='month-boundary-123')
    client.post('/api/transactions',headers=headers(),json=data)
    week=client.get('/api/summary?period=week',headers=headers()).json
    assert week['start']=='2026-09-28' and week['totals'][0]['amount']==3000
    month=client.get('/api/summary?period=month',headers=headers()).json
    assert month['totals'][0]['amount']==2000

def test_menu_close_and_reopen(access_client):
    client,calls,_=access_client
    assert message(client,123,'/menu').status_code==200
    assert any('keyboard' in body.get('reply_markup',{}) for _,body in calls)
    calls.clear()
    assert message(client,123,'✕ បិទ Menu / Close menu').status_code==200
    assert calls[-1][1]['reply_markup']=={'remove_keyboard':True}
    calls.clear()
    message(client,123,'/id')
    assert 'reply_markup' not in calls[-1][1]
    calls.clear()
    message(client,123,'/menu')
    assert any('keyboard' in body.get('reply_markup',{}) for _,body in calls)

def test_bulk_selected_delete_is_owner_scoped_and_single_use(client):
    mine=client.post('/api/transactions',json=payload(),headers=headers()).json['id']
    theirs=client.post('/api/transactions',json=payload(),headers=headers(456)).json['id']
    endpoint='/api/transactions/delete-preview'
    assert client.post(endpoint,json={'scope':'all'}).status_code==401
    assert client.post(endpoint,json={'scope':'selected','ids':[mine,theirs]},headers=headers()).status_code==404
    preview=client.post(endpoint,json={'scope':'selected','ids':[mine]},headers=headers()).json
    assert preview['count']==1
    body={'token':preview['token'],'confirmation':'DELETE'}
    assert client.post('/api/transactions/delete-confirm',json=body,headers=headers(456)).status_code==409
    assert client.post('/api/transactions/delete-confirm',json={**body,'confirmation':'yes'},headers=headers()).status_code==400
    assert client.post('/api/transactions/delete-confirm',json=body,headers=headers()).json['deleted']==1
    assert client.post('/api/transactions/delete-confirm',json=body,headers=headers()).status_code==409
    assert len(client.get('/api/data?month=2026-01',headers=headers(456)).json['transactions'])==1


def test_bulk_all_snapshot_preserves_later_entries_and_goals(client):
    a=payload();client.post('/api/transactions',json=a,headers=headers())
    b={**a,'request_id':'second-request','currency':'KHR','amount':'12000','day':'2025-12-20'}
    client.post('/api/transactions',json=b,headers=headers())
    client.post('/api/goals',json={'title':'Laptop','currency':'USD','target':'500','saved':'20','request_id':'goal-new-test'},headers=headers())
    preview=client.post('/api/transactions/delete-preview',json={'scope':'all'},headers=headers()).json
    assert preview['count']==2
    client.post('/api/transactions',json={**a,'request_id':'after-preview'},headers=headers())
    response=client.post('/api/transactions/delete-confirm',json={'token':preview['token'],'confirmation':'DELETE'},headers=headers())
    assert response.json['deleted']==2
    assert len(client.get('/api/data?month=2026-01',headers=headers()).json['transactions'])==1
    assert len(client.get('/api/goals',headers=headers()).json['goals'])==1


def test_bulk_preview_invalidates_previous_and_expires(client,monkeypatch):
    client.post('/api/transactions',json=payload(),headers=headers())
    preview=lambda:client.post('/api/transactions/delete-preview',json={'scope':'all'},headers=headers()).json
    old=preview();new=preview()
    assert client.post('/api/transactions/delete-confirm',json={'token':old['token'],'confirmation':'DELETE'},headers=headers()).status_code==409
    now=time.time();monkeypatch.setattr('app.time.time',lambda:now+301)
    assert client.post('/api/transactions/delete-confirm',json={'token':new['token'],'confirmation':'DELETE'},headers=headers()).status_code==409
    assert len(client.get('/api/data?month=2026-01',headers=headers()).json['transactions'])==1


@pytest.mark.parametrize('body',[{'scope':'other'},{'scope':'selected','ids':[]},{'scope':'selected','ids':[True]},{'scope':'selected','ids':'1'}])
def test_bulk_preview_rejects_invalid_selection(client,body):
    assert client.post('/api/transactions/delete-preview',json=body,headers=headers()).status_code==400

def test_trash_restore_photo_and_permanent_delete(client):
    import io
    from PIL import Image
    photo=io.BytesIO();Image.new('RGB',(32,32),'green').save(photo,format='PNG')
    identity=client.post('/api/transactions',json=payload(),headers=headers()).json['id']
    url=f'/api/transactions/{identity}/photo'
    assert client.put(url,data=photo.getvalue(),content_type='image/png',headers=headers(456)).status_code==404
    assert client.put(url,data=b'not an image',content_type='image/png',headers=headers()).status_code==400
    assert client.put(url,data=photo.getvalue(),content_type='image/png',headers=headers()).status_code==200
    response=client.get(url,headers=headers());assert response.mimetype=='image/jpeg'
    assert response.headers['Cache-Control']=='no-store'
    assert client.get(url,headers=headers(456)).status_code==404
    assert client.delete(f'/api/transactions/{identity}',headers=headers()).status_code==200
    trashed=client.get('/api/trash',headers=headers()).json['entries'][0]
    assert not client.get('/api/trash',headers=headers(456)).json['entries']
    assert client.post('/api/transactions',json=payload(),headers=headers()).status_code==409
    assert client.post(f"/api/trash/{trashed['id']}/restore",headers=headers(456)).status_code==404
    restored=client.post(f"/api/trash/{trashed['id']}/restore",headers=headers()).json['id']
    assert client.get(f'/api/transactions/{restored}/photo',headers=headers()).status_code==200
    assert client.post(f"/api/trash/{trashed['id']}/restore",headers=headers()).status_code==404
    client.delete(f'/api/transactions/{restored}',headers=headers())
    tid=client.get('/api/trash',headers=headers()).json['entries'][0]['id']
    assert client.delete(f'/api/trash/{tid}',json={},headers=headers()).status_code==400
    assert client.delete(f'/api/trash/{tid}',json={'confirmation':'DELETE'},headers=headers()).status_code==200
    assert client.get('/api/trash',headers=headers()).json['total']==0


def test_profile_persists_and_is_owner_scoped(client):
    assert client.put('/api/profile',json={'name':'Thearith','bio':'Student'},headers=headers()).status_code==200
    assert client.get('/api/data',headers=headers()).json['user']['name']=='Thearith'
    assert client.get('/api/profile',headers=headers()).json['bio']=='Student'
    assert client.get('/api/profile',headers=headers(456)).json['name']==''
    assert client.put('/api/profile',json={'name':' '},headers=headers()).status_code==400
    assert client.put('/api/profile',json={'name':'A'*81},headers=headers()).status_code==400


def test_category_limits_and_comparison_after_restore(client):
    a=payload();identity=client.post('/api/transactions',json=a,headers=headers()).json['id']
    b={**a,'amount':'10','day':'2025-12-10','request_id':'previous-month-test'}
    client.post('/api/transactions',json=b,headers=headers())
    client.post('/api/transactions',json={**b,'amount':'100'},headers=headers(456))
    limit={'month':'2026-01','currency':'USD','category':'food','amount':'20'}
    assert client.put('/api/category-budgets',json=limit,headers=headers()).status_code==200
    assert client.put('/api/category-budgets',json={**limit,'category':'salary'},headers=headers()).status_code==400
    assert client.put('/api/category-budgets',json={**limit,'category':['food']},headers=headers()).status_code==400
    assert client.get('/api/category-budgets?month=2026-01',headers=headers()).json['budgets'][0]['spent']==1234
    updated=client.put('/api/category-budgets',json={**limit,'amount':'25'},headers=headers())
    assert updated.status_code==200
    saved=client.get('/api/category-budgets?month=2026-01',headers=headers()).json['budgets']
    assert len(saved)==1 and saved[0]['amount']==2500 and saved[0]['spent']==1234
    assert not client.get('/api/category-budgets?month=2026-01',headers=headers(456)).json['budgets']
    data=client.get('/api/compare?month=2026-01',headers=headers()).json
    assert data['previous_month']=='2025-12'
    assert data['totals']['previous']['USD']['expense']==1000
    assert data['totals']['current']['USD']['expense']==1234
    client.delete(f'/api/transactions/{identity}',headers=headers())
    assert client.get('/api/compare?month=2026-01',headers=headers()).json['totals']['current']['USD']['expense']==0
    tid=client.get('/api/trash',headers=headers()).json['entries'][0]['id']
    client.post(f'/api/trash/{tid}/restore',headers=headers())
    assert client.get('/api/category-budgets?month=2026-01',headers=headers()).json['budgets'][0]['spent']==1234
    client.delete('/api/category-budgets',json=limit,headers=headers())
    assert not client.get('/api/category-budgets?month=2026-01',headers=headers()).json['budgets']


def test_bulk_delete_moves_all_selected_to_trash(client):
    for i in range(3):client.post('/api/transactions',json={**payload(),'request_id':f'bulk-trash-{i}'},headers=headers())
    batch=client.post('/api/transactions/delete-preview',json={'scope':'all'},headers=headers()).json
    assert client.post('/api/transactions/delete-confirm',json={'token':batch['token'],'confirmation':'DELETE'},headers=headers()).json['deleted']==3
    assert client.get('/api/trash',headers=headers()).json['total']==3
    assert not client.get('/api/data?month=2026-01',headers=headers()).json['transactions']


def test_photo_size_and_json_limit(client):
    identity=client.post('/api/transactions',json=payload(),headers=headers()).json['id']
    assert client.put(f'/api/transactions/{identity}/photo',data=b'x'*(2*1024*1024+1),headers=headers()).status_code==400
    assert client.put('/api/profile',json={'name':'x','bio':'x'*17000},headers=headers()).status_code==413


def test_favorites_crud_is_scoped_and_validated(client):
    assert client.get('/api/favorites',headers=headers()).json=={'favorites':[]}
    favorite={'title':'Morning coffee','kind':'expense','category':'coffee','amount':'2.50','currency':'USD','account':'cash','note':'Latte'}
    assert client.post('/api/favorites',json=favorite,headers=headers()).status_code==201
    saved=client.get('/api/favorites',headers=headers()).json['favorites']
    assert len(saved)==1 and saved[0]['amount']==250
    assert client.get('/api/favorites',headers=headers(456)).json['favorites']==[]
    identity=saved[0]['id']
    assert client.delete(f'/api/favorites/{identity}',headers=headers(456)).status_code==404
    assert client.delete(f'/api/favorites/{identity}',headers=headers()).status_code==200
    assert client.get('/api/favorites',headers=headers()).json['favorites']==[]
    assert client.post('/api/favorites',json={**favorite,'title':' '},headers=headers()).status_code==400
    assert client.post('/api/favorites',json={**favorite,'category':'salary'},headers=headers()).status_code==400
    assert client.post('/api/favorites',json={**favorite,'kind':'income','category':'salary'},headers=headers()).status_code==201


def test_favorite_limit(client):
    for index in range(12):
        favorite={'title':f'Favorite {index}','kind':'expense','category':'food','amount':'10','currency':'KHR','account':'cash','note':''}
        assert client.post('/api/favorites',json=favorite,headers=headers()).status_code==201
    favorite={'title':'Thirteenth','kind':'expense','category':'food','amount':'10','currency':'KHR','account':'cash','note':''}
    assert client.post('/api/favorites',json=favorite,headers=headers()).status_code==409


def test_fx_display_settings_are_validated_and_private(client):
    assert client.get('/api/fx',headers=headers()).json=={'base_currency':'KHR','rate_khr_per_usd':4000.0}
    saved=client.put('/api/fx',json={'base_currency':'USD','rate_khr_per_usd':'4102.5'},headers=headers())
    assert saved.status_code==200
    assert saved.json=={'ok':True,'base_currency':'USD','rate_khr_per_usd':4102.5}
    assert client.get('/api/fx',headers=headers()).json=={'base_currency':'USD','rate_khr_per_usd':4102.5}
    assert client.get('/api/fx',headers=headers(456)).json=={'base_currency':'KHR','rate_khr_per_usd':4000.0}
    for currency,rate in [('EUR',4000),('KHR',0),('USD',100001),('USD','NaN'),('USD','4.12345')]:
        assert client.put('/api/fx',json={'base_currency':currency,'rate_khr_per_usd':rate},headers=headers()).status_code==400


def test_custom_categories_crud_ownership_and_transaction_use(client):
    created=client.post('/api/categories',json={'name':'Pets','kind':'expense'},headers=headers())
    assert created.status_code==201
    category=created.json
    assert category['name']=='Pets' and category['kind']=='expense'
    assert client.get('/api/categories',headers=headers(456)).json=={'categories':[]}
    entry={**payload(),'currency':'KHR','amount':'2500','category':category['key']}
    assert client.post('/api/transactions',json=entry,headers=headers()).status_code==201
    assert client.post('/api/transactions',json={**entry,'request_id':'wrong-owner-category'},headers=headers(456)).status_code==400
    assert client.put('/api/categories/'+category['key'],json={'name':'Pet care'},headers=headers()).status_code==200
    assert client.delete('/api/categories/'+category['key'],headers=headers()).status_code==409
    assert client.put('/api/categories/'+category['key'],json={'name':'Pets'},headers=headers(456)).status_code==404
    income=client.post('/api/categories',json={'name':'Gift money','kind':'income'},headers=headers()).json
    wrong_type={**payload(),'category':income['key'],'request_id':'wrong-category-type'}
    assert client.post('/api/transactions',json=wrong_type,headers=headers()).status_code==400
    assert client.put('/api/category-budgets',json={'month':'2026-01','currency':'KHR','category':income['key'],'amount':'20'},headers=headers()).status_code==400
    assert client.delete('/api/categories/'+income['key'],headers=headers()).status_code==200
    assert client.post('/api/categories',json={'name':'  ','kind':'both'},headers=headers()).status_code==400


def test_personal_debts_crud_proof_photo_and_user_isolation(client):
    import io
    from PIL import Image
    data={'direction':'lent','person':'Sokha','amount':'25.50','currency':'USD','due_date':'2026-12-01','note':'Dinner share'}
    created=client.post('/api/debts',json=data,headers=headers())
    assert created.status_code==201
    identity=created.json['id']
    record=client.get('/api/debts',headers=headers()).json['debts'][0]
    assert record['person']=='Sokha' and record['amount']==2550 and record['status']=='open' and record['has_photo'] is False
    history=client.get(f'/api/debts/{identity}/history',headers=headers()).json['events']
    assert len(history)==1 and history[0]['action']=='created' and history[0]['details']['after']['due_date']=='2026-12-01'
    assert client.get('/api/debts',headers=headers(uid=456)).json=={'debts':[]}
    assert client.get(f'/api/debts/{identity}/history',headers=headers(uid=456)).status_code==404
    assert client.put(f'/api/debts/{identity}',json={**data,'person':'New name'},headers=headers(uid=456)).status_code==404
    updated=client.put(f'/api/debts/{identity}',json={**data,'person':'Sokha Dara','due_date':'2026-12-15'},headers=headers())
    assert updated.status_code==200
    history=client.get(f'/api/debts/{identity}/history',headers=headers()).json['events']
    assert history[0]['action']=='updated' and history[0]['details']['before']['due_date']=='2026-12-01'
    assert history[0]['details']['after']['due_date']=='2026-12-15' and 'due_date' in history[0]['details']['changed_fields']
    assert client.put(f'/api/debts/{identity}/status',json={'status':'settled'},headers=headers(uid=456)).status_code==404
    image=io.BytesIO();Image.new('RGB',(40,40),'blue').save(image,format='PNG')
    photo_url=f'/api/debts/{identity}/photo'
    assert client.put(photo_url,data=image.getvalue(),content_type='image/png',headers=headers(uid=456)).status_code==404
    assert client.put(photo_url,data=image.getvalue(),content_type='image/png',headers=headers()).status_code==200
    photo=client.get(photo_url,headers=headers())
    assert photo.status_code==200 and photo.mimetype=='image/jpeg'
    assert client.get(photo_url,headers=headers(uid=456)).status_code==404
    assert client.get('/api/debts?status=settled',headers=headers()).json['debts']==[]
    assert client.put(f'/api/debts/{identity}/status',json={'status':'settled'},headers=headers()).status_code==409
    payment=client.post(f'/api/debts/{identity}/payments',json={'amount':'25.50','paid_on':'2026-12-01'},headers=headers())
    assert payment.status_code==201 and payment.json['remaining']==0
    assert client.put(f'/api/debts/{identity}/status',json={'status':'settled'},headers=headers()).status_code==200
    assert client.get('/api/debts?status=settled',headers=headers()).json['debts'][0]['settled_at']
    assert client.put(f'/api/debts/{identity}/status',json={'status':'open'},headers=headers()).status_code==409
    assert client.delete(f'/api/debts/{identity}/payments/{payment.json["id"]}',headers=headers()).status_code==200
    actions=[event['action'] for event in client.get(f'/api/debts/{identity}/history',headers=headers()).json['events']]
    assert 'settled' in actions and 'reopened' in actions and 'photo_attached' in actions and 'payment_added' in actions and 'payment_deleted' in actions
    assert client.put(f'/api/debts/{identity}',json={**data,'person':'Sokha'},headers=headers()).status_code==200
    assert client.delete(f'/api/debts/{identity}',headers=headers(uid=456)).status_code==404
    assert client.delete(f'/api/debts/{identity}',headers=headers()).status_code==200
    assert client.get(photo_url,headers=headers()).status_code==404
    assert client.post('/api/debts',json={**data,'direction':'other'},headers=headers()).status_code==400
    assert client.post('/api/debts',json={**data,'person':' '},headers=headers()).status_code==400

def test_personal_debt_can_be_created_without_associated_person(client):
    data={'direction':'borrowed','amount':'15','currency':'USD','note':'Book purchase'}
    response=client.post('/api/debts',json=data,headers=headers())
    assert response.status_code==201
    saved=client.get('/api/debts',headers=headers()).json['debts'][0]
    assert saved['person']=='' and saved['note']=='Book purchase'


def test_debt_partial_repayments_crud_balance_and_audit_history(client):
    data={'direction':'lent','person':'Sokha','amount':'25.50','currency':'USD','note':'Loan'}
    debt=client.post('/api/debts',json=data,headers=headers()).json['id']
    url=f'/api/debts/{debt}/payments'
    first=client.post(url,json={'amount':'10.50','paid_on':'2026-10-01','note':'First'},headers=headers())
    assert first.status_code==201 and first.json['remaining']==1500
    payment_id=first.json['id']
    assert client.put(f'/api/debts/{debt}',json={**data,'amount':'10.00'},headers=headers()).status_code==400
    assert client.put(f'/api/debts/{debt}',json={**data,'currency':'KHR'},headers=headers()).status_code==400
    assert client.post(url,json={'amount':'15.01','paid_on':'2026-10-02'},headers=headers()).status_code==400
    assert client.post(url,json={'amount':'15.00','paid_on':'2026-10-02'},headers=headers(uid=456)).status_code==404
    second=client.post(url,json={'amount':'15.00','paid_on':'2026-10-02','note':'Final'},headers=headers())
    assert second.status_code==201 and second.json['remaining']==0
    record=client.get('/api/debts',headers=headers()).json['debts'][0]
    assert record['paid_total']==2550 and record['remaining']==0 and record['status']=='settled'
    assert client.put(f'/api/debts/{debt}',json={**data,'amount':'26.00'},headers=headers()).status_code==200
    record=client.get('/api/debts',headers=headers()).json['debts'][0]
    assert record['remaining']==50 and record['status']=='open'
    assert client.put(f'/api/debts/{debt}',json=data,headers=headers()).status_code==200
    payment2=second.json['id']
    edited=client.put(f'{url}/{payment2}',json={'amount':'14.00','paid_on':'2026-10-03','note':'Corrected'},headers=headers())
    assert edited.status_code==200 and edited.json['remaining']==100
    record=client.get('/api/debts',headers=headers()).json['debts'][0]
    assert record['status']=='open' and record['remaining']==100
    assert client.put(f'{url}/{payment2}',json={'amount':'15.01','paid_on':'2026-10-03'},headers=headers()).status_code==400
    assert client.delete(f'{url}/{payment_id}',headers=headers(uid=456)).status_code==404
    assert client.delete(f'{url}/{payment_id}',headers=headers()).json['remaining']==1150
    record=client.get('/api/debts',headers=headers()).json['debts'][0]
    assert record['paid_total']==1400 and record['remaining']==1150 and record['status']=='open'
    actions=[event['action'] for event in client.get(f'/api/debts/{debt}/history',headers=headers()).json['events']]
    assert 'payment_added' in actions and 'payment_updated' in actions and 'payment_deleted' in actions
