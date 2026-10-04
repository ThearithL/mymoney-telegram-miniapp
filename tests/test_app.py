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
