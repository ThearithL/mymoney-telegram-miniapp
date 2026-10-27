import hashlib
import hmac
import json
import time
from datetime import date, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import insert

from app import create_app, transactions, personal_tables
from notifications import debt_stage, debt_line

OWNER = 1219084924
OTHER = 987654321
TOKEN = '12345:test-token'
TZ = ZoneInfo('Asia/Phnom_Penh')


def at(year, month, day, hour):
    return datetime(year, month, day, hour, 0, tzinfo=TZ)


def headers(uid=OWNER):
    data = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': uid, 'first_name': 'Test'})}
    key = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    data['hash'] = hmac.new(key, '\n'.join(f'{k}={v}' for k, v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
    return {'Authorization': 'tma ' + urlencode(data)}


@pytest.fixture
def project(tmp_path, monkeypatch):
    calls = []
    state = {'ok': True}

    class Reply:
        @property
        def ok(self):
            return state['ok']

        def json(self):
            return {'ok': state['ok']}

    def post(url, json, **kwargs):
        calls.append((url.rsplit('/', 1)[-1], json))
        return Reply()

    monkeypatch.setattr('requests.post', post)
    monkeypatch.setenv('REMINDER_SECRET', 'reminder-secret-for-tests')
    config = {'TESTING': True, 'DATABASE_URL': 'sqlite:///' + str(tmp_path / 'test.db'),
              'BOT_TOKEN': TOKEN, 'ADMIN_USER_ID': str(OWNER), 'ALLOWED_USER_IDS': str(OTHER),
              'WEBHOOK_SECRET': 'testing-webhook-secret', 'APP_URL': 'https://example.test',
              'FLASK_SECRET_KEY': 'test-signing-key', 'ADMIN_PASSWORD': 'test-password'}
    app = create_app(config)
    yield app, app.test_client(), calls, state
    app.extensions['engine'].dispose()


def messages(calls):
    return [payload for method, payload in calls if method == 'sendMessage']


def settings(client, uid=OWNER, **overrides):
    body = {'daily_enabled': False, 'daily_hour': 20, 'debt_enabled': True, 'debt_days_before': 1, **overrides}
    return client.put('/api/notifications', json=body, headers=headers(uid))


def add_debt(client, due, direction='lent', person='Sokha', amount='25.50', uid=OWNER):
    response = client.post('/api/debts', json={'direction': direction, 'person': person, 'amount': amount,
        'currency': 'USD', 'due_date': due, 'note': ''}, headers=headers(uid))
    assert response.status_code == 201
    return response.json['id']


def test_stage_rules():
    assert debt_stage(0, 1) == 'today'
    assert debt_stage(1, 1) == 'soon'
    assert debt_stage(2, 1) is None
    assert debt_stage(3, 3) == 'soon'
    assert debt_stage(-1, 1) == 'overdue'
    assert debt_stage(-14, 1) == 'overdue'
    assert debt_stage(-15, 1) is None
    assert debt_stage(1, 0) is None


def test_debt_line_wording():
    lent = {'direction': 'lent', 'person': 'Sokha', 'currency': 'USD'}
    borrowed = {'direction': 'borrowed', 'person': 'Dara', 'currency': 'KHR'}
    assert 'Sokha owes you' in debt_line(lent, 2550, 1) and '25.50 USD' in debt_line(lent, 2550, 1)
    assert 'due in 1 day' in debt_line(lent, 2550, 1)
    assert 'You owe Dara' in debt_line(borrowed, 40000, 0) and 'due today' in debt_line(borrowed, 40000, 0)
    assert '3 days overdue' in debt_line(borrowed, 40000, -3)


def test_settings_defaults_roundtrip_validation_and_isolation(project):
    app, client, calls, state = project
    assert client.get('/api/notifications').status_code == 401
    assert client.get('/api/notifications', headers=headers()).json == {
        'daily_enabled': False, 'daily_hour': 20, 'debt_enabled': True, 'debt_days_before': 1,
        'bill_enabled': True, 'weekly_enabled': False}
    saved = settings(client, daily_enabled=True, daily_hour=7, debt_days_before=3)
    assert saved.status_code == 200
    assert client.get('/api/notifications', headers=headers()).json == {
        'daily_enabled': True, 'daily_hour': 7, 'debt_enabled': True, 'debt_days_before': 3,
        'bill_enabled': True, 'weekly_enabled': False}
    assert client.get('/api/notifications', headers=headers(OTHER)).json['daily_enabled'] is False
    for bad in ({'daily_hour': 24}, {'daily_hour': -1}, {'debt_days_before': 8}, {'daily_hour': '9'},
                {'daily_enabled': 1}, {'debt_enabled': 'yes'}, {'daily_hour': True}):
        assert settings(client, **bad).status_code == 400
    assert client.put('/api/notifications', json={'daily_hour': 9}, headers=headers()).status_code == 400


def test_test_message_is_sent_and_rate_limited(project):
    app, client, calls, state = project
    assert client.post('/api/notifications/test', headers=headers()).json == {'ok': True}
    sent = messages(calls)
    assert len(sent) == 1 and sent[0]['chat_id'] == OWNER
    assert sent[0]['reply_markup']['inline_keyboard'][0][0]['web_app']['url'] == 'https://example.test'
    assert client.post('/api/notifications/test', headers=headers()).status_code == 429
    state['ok'] = False
    assert client.post('/api/notifications/test', headers=headers(OTHER)).status_code == 502


def test_daily_reminder_window_dedupe_and_skip_when_logged(project):
    app, client, calls, state = project
    run = app.extensions['run_reminders']
    settings(client, daily_enabled=True, daily_hour=20)
    assert run(at(2026, 12, 1, 19))['daily'] == 0          # too early
    assert run(at(2026, 12, 1, 23))['daily'] == 0          # window (20-22) has passed
    assert run(at(2026, 12, 1, 20))['daily'] == 1
    assert run(at(2026, 12, 1, 21))['daily'] == 0          # already sent today
    assert len(messages(calls)) == 1 and messages(calls)[0]['chat_id'] == OWNER
    assert run(at(2026, 12, 2, 20))['daily'] == 1          # a new day sends again
    # Skipped when something was already logged that day.
    with app.extensions['engine'].begin() as conn:
        conn.execute(insert(transactions).values(user_id=OWNER, amount=100, currency='USD', kind='expense',
            day=date(2026, 12, 3), category='food', account='cash', note='', request_id='logged-today'))
    assert run(at(2026, 12, 3, 20))['daily'] == 0
    # Disabled users get nothing.
    settings(client, daily_enabled=False)
    assert run(at(2026, 12, 4, 20))['daily'] == 0


def test_failed_delivery_is_retried_not_lost(project):
    app, client, calls, state = project
    run = app.extensions['run_reminders']
    settings(client, daily_enabled=True, daily_hour=20)
    state['ok'] = False
    result = run(at(2026, 12, 1, 20))
    assert result['daily'] == 0 and result['failed'] == 1
    state['ok'] = True
    assert run(at(2026, 12, 1, 20))['daily'] == 1


def test_debt_reminders_stage_once_and_group_into_one_message(project):
    app, client, calls, state = project
    run = app.extensions['run_reminders']
    soon = add_debt(client, '2026-12-02', 'lent', 'Sokha')
    add_debt(client, '2026-12-01', 'borrowed', 'Dara', '10.00')
    add_debt(client, '2026-12-20', 'lent', 'Later')                        # outside the window
    add_debt(client, None, 'lent', 'NoDate')                                # no due date
    assert run(at(2026, 12, 1, 8))['debt'] == 0                             # before send hour
    assert run(at(2026, 12, 1, 9))['debt'] == 2
    sent = messages(calls)
    assert len(sent) == 1
    assert 'Sokha owes you' in sent[0]['text'] and 'You owe Dara' in sent[0]['text']
    assert 'Later' not in sent[0]['text'] and 'NoDate' not in sent[0]['text']
    assert run(at(2026, 12, 1, 15))['debt'] == 0                            # same stage never repeats
    # The next day: Sokha's debt is due today (new stage); Dara's is now overdue (new stage).
    assert run(at(2026, 12, 2, 9))['debt'] == 2
    # Deleted debts disappear; opted-out users are left alone.
    assert client.delete(f'/api/debts/{soon}', headers=headers()).status_code == 200
    assert run(at(2026, 12, 3, 9))['debt'] == 0                             # Dara's overdue stage was already sent
    settings(client, debt_enabled=False)
    add_debt(client, '2026-12-04', person='Optout')
    assert run(at(2026, 12, 4, 9))['debt'] == 0


def test_debt_days_before_setting_and_changed_due_date(project):
    app, client, calls, state = project
    run = app.extensions['run_reminders']
    identity = add_debt(client, '2026-12-05')
    settings(client, debt_days_before=3)
    assert run(at(2026, 12, 1, 9))['debt'] == 0                             # 4 days away
    assert run(at(2026, 12, 2, 9))['debt'] == 1                             # 3 days away
    settings(client, debt_days_before=3)
    client.put(f'/api/debts/{identity}', json={'direction': 'lent', 'person': 'Sokha', 'amount': '25.50',
        'currency': 'USD', 'due_date': '2026-12-06', 'note': ''}, headers=headers())
    assert run(at(2026, 12, 3, 9))['debt'] == 1                             # new due date, new reminder


def test_each_user_only_hears_about_their_own_debts(project):
    app, client, calls, state = project
    run = app.extensions['run_reminders']
    add_debt(client, '2026-12-01', person='OwnerDebt')
    add_debt(client, '2026-12-01', person='OtherDebt', uid=OTHER)
    assert run(at(2026, 12, 1, 9))['debt'] == 2
    by_chat = {payload['chat_id']: payload['text'] for payload in messages(calls)}
    assert 'OwnerDebt' in by_chat[OWNER] and 'OtherDebt' not in by_chat[OWNER]
    assert 'OtherDebt' in by_chat[OTHER] and 'OwnerDebt' not in by_chat[OTHER]


def test_reminder_endpoint_requires_secret(project):
    app, client, calls, state = project
    assert client.get('/ops/reminders/wrong').status_code == 404
    response = client.get('/ops/reminders/reminder-secret-for-tests')
    assert response.status_code == 200 and response.json['ok'] is True
    assert set(response.json) >= {'daily', 'debt', 'skipped', 'failed'}


def test_notification_tables_are_registered_for_account_erasure(project):
    # Admin "erase user" deletes from every table in personal_tables that has a user_id.
    app, client, calls, state = project
    for name in ('notification_settings', 'notification_log'):
        assert name in personal_tables and 'user_id' in personal_tables[name].c
