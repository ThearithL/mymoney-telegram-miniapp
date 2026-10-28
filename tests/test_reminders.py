from datetime import datetime, timedelta

from reminders import parse_date, status_for, summarize
from tests.test_notifications import (OTHER, OWNER, TZ, headers,  # noqa: F401
                                      project)


def today():
    return datetime.now(TZ).date()


def make(client, uid=OWNER, **overrides):
    body = {'title': 'Call landlord', 'note': 'About the deposit', 'remind_date': today().isoformat(),
            **overrides}
    return client.post('/api/reminders', json=body, headers=headers(uid))


def test_parse_date_rejects_impossible_dates():
    assert parse_date('2026-11-05').isoformat() == '2026-11-05'
    for bad in ('2026-02-31', '2026-13-01', '31/02/2026', '2026-1-5', '', None, 5, '1999-01-01'):
        assert parse_date(bad) is None, bad


def test_status_and_summary():
    now = today()
    rows = [{'remind_date': now - timedelta(days=1)}, {'remind_date': now}, {'remind_date': now},
            {'remind_date': now + timedelta(days=7)}, {'remind_date': now + timedelta(days=8)}]
    assert [status_for(r['remind_date'], now) for r in rows] == ['overdue', 'today', 'today', 'week', 'later']
    assert summarize(rows, now) == {'overdue': 1, 'today': 2, 'week': 3, 'total': 5}


def test_crud_validation_sorting_and_isolation(project):
    app, client, calls, state = project
    assert client.get('/api/reminders').status_code == 401
    now = today()
    far = make(client, title='Far', remind_date=(now + timedelta(days=20)).isoformat())
    assert far.status_code == 201
    late = make(client, title='Late time', remind_date=now.isoformat(), remind_time='18:30', amount='5', currency='USD')
    early = make(client, title='Early time', remind_date=now.isoformat(), remind_time='08:00')
    untimed = make(client, title='No time', remind_date=now.isoformat())
    past = make(client, title='Past', remind_date=(now - timedelta(days=2)).isoformat())
    assert all(r.status_code == 201 for r in (late, early, untimed, past))
    assert late.json['remind_date'] == now.isoformat()

    for bad in ({'title': ' '}, {'title': 'x' * 81}, {'remind_date': '2026-02-31'}, {'remind_date': '05/11/2026'},
                {'remind_date': None}, {'remind_time': '25:00'}, {'remind_time': '8:00'}, {'ref_type': 'loan'},
                {'ref_type': 'bill'}, {'amount': '-3', 'currency': 'USD'}, {'amount': '3', 'currency': 'EUR'},
                {'note': 'n' * 501}):
        assert make(client, **bad).status_code == 400, bad

    data = client.get('/api/reminders', headers=headers()).json
    assert [r['title'] for r in data['items']] == ['Past', 'Early time', 'Late time', 'No time', 'Far']
    assert data['summary'] == {'overdue': 1, 'today': 3, 'week': 3, 'total': 5}
    assert [r['status'] for r in data['items']] == ['overdue', 'today', 'today', 'today', 'later']
    assert next(r for r in data['items'] if r['title'] == 'Late time')['amount'] == 500
    assert client.get('/api/reminders', headers=headers(OTHER)).json['items'] == []

    rid = far.json['id']
    assert client.put(f'/api/reminders/{rid}', json={'title': 'x', 'remind_date': now.isoformat()},
                      headers=headers(OTHER)).status_code == 404
    assert client.delete(f'/api/reminders/{rid}', headers=headers(OTHER)).status_code == 404
    edited = client.put(f'/api/reminders/{rid}', json={'title': 'Far edited', 'remind_date': now.isoformat(),
                                                        'remind_time': ''}, headers=headers())
    assert edited.status_code == 200 and edited.json['remind_date'] == now.isoformat()
    assert client.put(f'/api/reminders/{rid}', json={'title': 'Bad', 'remind_date': '2026-02-30'},
                      headers=headers()).status_code == 400
    assert client.delete(f'/api/reminders/{rid}', headers=headers()).status_code == 200
    assert client.delete(f'/api/reminders/{rid}', headers=headers()).status_code == 404


def test_linked_records_must_belong_to_the_user(project):
    app, client, calls, state = project
    bill = client.post('/api/recurring', json={'title': 'Rent', 'kind': 'expense', 'amount': '200',
        'currency': 'USD', 'category': 'bills', 'account': 'bank', 'day_of_month': 5, 'remind_days': 1},
        headers=headers()).json['id']
    goal = client.post('/api/goals', json={'title': 'Laptop', 'currency': 'USD', 'target': '500', 'saved': '0',
        'request_id': 'goal-request-reminder'}, headers=headers())
    debt = client.post('/api/debts', json={'direction': 'lent', 'amount': '10', 'currency': 'USD',
        'due_date': None, 'note': 'x', 'person': 'Sok'}, headers=headers())
    ok = make(client, ref_type='bill', ref_id=bill)
    assert ok.status_code == 201
    assert make(client, uid=OTHER, ref_type='bill', ref_id=bill).status_code == 404
    assert make(client, ref_type='goal', ref_id=999999).status_code == 404
    if goal.status_code in (200, 201):
        assert make(client, ref_type='goal', ref_id=goal.json['id']).status_code == 201
    row = client.get('/api/reminders', headers=headers()).json['items'][0]
    assert row['ref_type'] == 'bill' and row['ref_id'] == bill
    # a general reminder ignores any ref_id sent along
    general = make(client, ref_type='general', ref_id=5).json['id']
    assert next(r for r in client.get('/api/reminders', headers=headers()).json['items']
                if r['id'] == general)['ref_id'] is None


def test_feed_lists_due_and_overdue_reminders_only(project):
    app, client, calls, state = project
    now = today()
    make(client, title='Overdue', remind_date=(now - timedelta(days=1)).isoformat())
    make(client, title='Today', remind_date=now.isoformat())
    make(client, title='Tomorrow', remind_date=(now + timedelta(days=1)).isoformat())
    feed = client.get('/api/notifications/feed', headers=headers()).json['items']
    reminders = {i['data']['title']: i for i in feed if i['type'] == 'reminder'}
    assert set(reminders) == {'Overdue', 'Today'}
    assert reminders['Overdue']['level'] == 'danger' and reminders['Today']['level'] == 'warn'
    assert reminders['Today']['id'].startswith('reminder:')


def test_telegram_reminder_sent_once_at_its_time(project):
    from tests.test_notifications import at, messages
    app, client, calls, state = project
    now = today()
    make(client, title='Timed', remind_date=now.isoformat(), remind_time='15:30', amount='5', currency='USD')
    make(client, title='Untimed', remind_date=now.isoformat())
    make(client, title='Tomorrow', remind_date=(now + timedelta(days=1)).isoformat())
    make(client, title='Ancient', remind_date=(now - timedelta(days=10)).isoformat())
    run = app.extensions['run_reminders']
    assert run(at(now.year, now.month, now.day, 7))['custom'] == 0
    assert run(at(now.year, now.month, now.day, 9))['custom'] == 1      # only the untimed one
    sent = ' '.join(m['text'] for m in messages(calls))
    assert 'Untimed' in sent and 'Timed' not in sent.replace('Untimed', '')
    assert run(at(now.year, now.month, now.day, 16))['custom'] == 1     # the timed one now
    assert run(at(now.year, now.month, now.day, 17))['custom'] == 0     # never twice
    text = messages(calls)[-1]['text']
    assert 'Timed' in text and '5.00 USD' in text and now.strftime('%d/%m/%Y') in text
    assert 'Tomorrow' not in ' '.join(m['text'] for m in messages(calls))


def test_failed_telegram_send_is_retried(project):
    from tests.test_notifications import at
    app, client, calls, state = project
    now = today()
    make(client, title='Retry me', remind_date=now.isoformat())
    run = app.extensions['run_reminders']
    state['ok'] = False
    assert run(at(now.year, now.month, now.day, 10))['failed'] == 1
    state['ok'] = True
    assert run(at(now.year, now.month, now.day, 10))['custom'] == 1
