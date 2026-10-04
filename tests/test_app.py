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
        response=client.put('/api/budget',json={'month':'2026-01','currency':currency,'amount':amount},headers=headers())
        assert response.status_code==200
        assert response.json['amount']==(10025 if currency=='USD' else 200000)
    updated=client.put('/api/budget',json={'month':'2026-01','currency':'USD','amount':'200'},headers=headers())
    assert updated.json=={'ok':True,'month':'2026-01','currency':'USD','amount':20000}
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
    assert client.get('/api/category-budgets?month=2026-01',headers=headers()).json['budgets'][0]['spent']==1234
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
    assert client.post('/api/favorites',json={**favorite,'category':'salary'},headers=headers()).status_code==201


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
    assert client.put(f'/api/debts/{identity}/status',json={'status':'settled'},headers=headers()).status_code==200
    assert client.get('/api/debts?status=settled',headers=headers()).json['debts'][0]['settled_at']
    assert client.put(f'/api/debts/{identity}/status',json={'status':'open'},headers=headers()).status_code==200
    actions=[event['action'] for event in client.get(f'/api/debts/{identity}/history',headers=headers()).json['events']]
    assert 'settled' in actions and 'reopened' in actions and 'photo_attached' in actions
    assert client.put(f'/api/debts/{identity}',json={**data,'person':'Sokha'},headers=headers()).status_code==200
    assert client.delete(f'/api/debts/{identity}',headers=headers(uid=456)).status_code==404
    assert client.delete(f'/api/debts/{identity}',headers=headers()).status_code==200
    assert client.get(photo_url,headers=headers()).status_code==404
    assert client.post('/api/debts',json={**data,'direction':'other'},headers=headers()).status_code==400
    assert client.post('/api/debts',json={**data,'person':' '},headers=headers()).status_code==400
