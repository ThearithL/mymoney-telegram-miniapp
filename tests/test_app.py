import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
import pytest
from app import create_app

TOKEN = '123456:test-token'

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

@pytest.mark.parametrize('amount,currency', [('0','USD'),('-1','KHR'),('1.001','USD'),('1.1','KHR'),('NaN','USD'),('Infinity','USD'),('100','EUR')])
def test_rejects_invalid_money(client,amount,currency):
    data=payload();data.update(amount=amount,currency=currency)
    assert client.post('/api/transactions',json=data,headers=headers()).status_code==400

def test_budget_currency_and_month_isolation(client):
    for currency,amount in [('USD','100.25'),('KHR','200000')]:
        assert client.put('/api/budget',json={'month':'2026-01','currency':currency,'amount':amount},headers=headers()).status_code==200
    client.put('/api/budget',json={'month':'2026-01','currency':'USD','amount':'200'},headers=headers())
    budgets=client.get('/api/data?month=2026-01',headers=headers()).json['budgets']
    assert {b['currency']:b['amount'] for b in budgets}=={'USD':20000,'KHR':200000}
    assert not client.get('/api/data?month=2026-02',headers=headers()).json['budgets']
    assert not client.get('/api/data?month=2026-01',headers=headers(uid=456)).json['budgets']

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
    config = {'TESTING': True, 'BOT_TOKEN': TOKEN, 'ALLOWED_USER_IDS': '', 'ADMIN_USER_ID': '123',
        'DATABASE_URL': 'sqlite:///'+str(tmp_path/'access.db'), 'WEBHOOK_SECRET': 'secret', 'APP_URL':'https://example.com'}
    return create_app(config).test_client(), calls, config

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
