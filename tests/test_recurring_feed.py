from datetime import date, datetime, timedelta

from recurring import clamp_day, cycle_info
from tests.test_notifications import (OTHER, OWNER, TZ, add_debt, at, headers,  # noqa: F401
                                      messages, project, settings)


def bill(client, uid=OWNER, **overrides):
    body = {'title': 'Rent', 'kind': 'expense', 'amount': '200', 'currency': 'USD', 'category': 'bills',
            'account': 'bank', 'day_of_month': 5, 'remind_days': 2, **overrides}
    return client.post('/api/recurring', json=body, headers=headers(uid))


def item(day, created='2026-01-01', remind=1):
    return {'day_of_month': day, 'created_on': created, 'remind_days': remind}


def test_clamp_day_handles_short_months():
    assert clamp_day(2027, 2, 31) == date(2027, 2, 28)
    assert clamp_day(2028, 2, 30) == date(2028, 2, 29)
    assert clamp_day(2026, 4, 31) == date(2026, 4, 30)


def test_cycle_status_rules():
    today = date(2026, 10, 10)
    assert cycle_info(item(8), today, False)['status'] == 'overdue'
    assert cycle_info(item(10), today, False)['status'] == 'today'
    assert cycle_info(item(12), today, False)['status'] == 'soon'
    assert cycle_info(item(25), today, False)['status'] == 'upcoming'
    paid = cycle_info(item(8), today, True)
    assert paid['status'] == 'paid' and paid['due_date'] == '2026-11-08'
    # created after this month's due day: waits for next month instead of being overdue
    fresh = cycle_info(item(3, created='2026-10-09'), today, False)
    assert fresh['status'] == 'upcoming' and fresh['due_date'] == '2026-11-03'
    # December rolls into the next year
    assert cycle_info(item(5), date(2026, 12, 20), True)['due_date'] == '2027-01-05'


def test_recurring_crud_validation_isolation_and_single_post_per_month(project):
    app, client, calls, state = project
    assert client.get('/api/recurring').status_code == 401
    made = bill(client)
    assert made.status_code == 201
    identity = made.json['id']
    for bad in ({'title': ' '}, {'kind': 'gift'}, {'amount': '0'}, {'day_of_month': 32}, {'day_of_month': 0},
                {'day_of_month': '5'}, {'remind_days': 9}, {'category': 'salary'}, {'category': 'nope'},
                {'account': 'wallet'}, {'currency': 'EUR'}):
        assert bill(client, **bad).status_code == 400, bad
    listing = client.get('/api/recurring', headers=headers()).json
    assert [r['title'] for r in listing['items']] == ['Rent']
    assert listing['monthly_expense_totals'] == {'USD': 20000}
    assert client.get('/api/recurring', headers=headers(OTHER)).json['items'] == []
    assert client.put(f'/api/recurring/{identity}', json={'title': 'x'}, headers=headers(OTHER)).status_code in (400, 404)
    assert client.delete(f'/api/recurring/{identity}', headers=headers(OTHER)).status_code == 404
    assert client.post(f'/api/recurring/{identity}/post', headers=headers(OTHER)).status_code == 404

    first = client.post(f'/api/recurring/{identity}/post', headers=headers())
    assert first.status_code == 201
    assert client.post(f'/api/recurring/{identity}/post', headers=headers()).status_code == 409
    row = client.get('/api/recurring', headers=headers()).json['items'][0]
    assert row['status'] == 'paid' and row['posted_this_month'] is True
    month = datetime.now(TZ).strftime('%Y-%m')
    data = client.get('/api/data?month=' + month, headers=headers()).json
    posted = [t for t in data['transactions'] if t['note'] == 'Rent']
    assert len(posted) == 1 and posted[0]['amount'] == 20000 and posted[0]['category'] == 'bills'

    assert client.post(f'/api/recurring/{identity}/active', json={'active': False}, headers=headers()).status_code == 200
    assert client.get('/api/recurring', headers=headers()).json['items'][0]['status'] == 'paused'
    assert client.delete(f'/api/recurring/{identity}', headers=headers()).status_code == 200
    assert client.get('/api/recurring', headers=headers()).json['items'] == []


def test_paused_item_cannot_be_posted(project):
    app, client, calls, state = project
    identity = bill(client).json['id']
    client.post(f'/api/recurring/{identity}/active', json={'active': False}, headers=headers())
    assert client.post(f'/api/recurring/{identity}/post', headers=headers()).status_code == 409


def test_bill_reminder_sent_once_then_stops_after_payment(project):
    app, client, calls, state = project
    today = datetime.now(TZ).date()
    due_day = (today + timedelta(days=1)).day
    identity = bill(client, day_of_month=due_day, remind_days=2).json['id']
    # make sure the item is not treated as "created after the due date"
    engine = app.extensions['engine']
    from sqlalchemy import update
    from app import personal_tables
    table = personal_tables['recurring_items']
    with engine.begin() as conn:
        conn.execute(update(table).values(created_on='2020-01-01'))
    run = app.extensions['run_reminders']
    when = datetime(today.year, today.month, today.day, 10, tzinfo=TZ)
    first = run(when)
    if (today + timedelta(days=1)).month != today.month:  # month boundary: due date is next month
        return
    assert first['bill'] == 1
    sent = messages(calls)
    assert any('Rent' in m['text'] and 'due in 1 day' in m['text'] for m in sent)
    assert run(when)['bill'] == 0
    # before the send hour nothing is sent for a new user
    assert run(when.replace(hour=6))['bill'] == 0
    client.post(f'/api/recurring/{identity}/post', headers=headers())
    assert run(when)['bill'] == 0


def test_bill_reminders_respect_opt_out(project):
    app, client, calls, state = project
    today = datetime.now(TZ).date()
    bill(client, day_of_month=today.day, remind_days=0)
    from sqlalchemy import update
    from app import personal_tables
    with app.extensions['engine'].begin() as conn:
        conn.execute(update(personal_tables['recurring_items']).values(created_on='2020-01-01'))
    body = {'daily_enabled': False, 'daily_hour': 20, 'debt_enabled': True, 'debt_days_before': 1,
            'bill_enabled': False}
    assert client.put('/api/notifications', json=body, headers=headers()).json['bill_enabled'] is False
    when = datetime(today.year, today.month, today.day, 10, tzinfo=TZ)
    assert app.extensions['run_reminders'](when)['bill'] == 0
    assert client.put('/api/notifications', json={**body, 'bill_enabled': 'yes'}, headers=headers()).status_code == 400


def test_weekly_summary_sent_once_per_week(project):
    app, client, calls, state = project
    sunday = date(2026, 10, 25)  # a Sunday
    assert sunday.weekday() == 6
    for offset, amount, category in ((0, '10', 'food'), (2, '30', 'transport'), (3, '5', 'food')):
        client.post('/api/transactions', json={'kind': 'expense', 'amount': amount, 'currency': 'USD',
            'category': category, 'account': 'cash', 'note': 'x', 'day': (sunday - timedelta(days=6 - offset)).isoformat(),
            'request_id': f'weekly-test-{offset}'}, headers=headers())
    body = {'daily_enabled': False, 'daily_hour': 20, 'debt_enabled': True, 'debt_days_before': 1,
            'weekly_enabled': True}
    client.put('/api/notifications', json=body, headers=headers())
    run = app.extensions['run_reminders']
    assert run(at(2026, 10, 25, 12))['weekly'] == 0          # too early on Sunday
    assert run(at(2026, 10, 27, 12))['weekly'] == 0          # Tuesday
    assert run(at(2026, 10, 25, 20))['weekly'] == 1
    text = messages(calls)[-1]['text']
    assert 'Weekly summary' in text and '45.00 USD' in text and 'transport' in text and '30.00 USD' in text
    assert run(at(2026, 10, 25, 21))['weekly'] == 0          # same week, already sent
    assert run(at(2026, 10, 26, 9))['weekly'] == 0           # Monday morning catch-up is also deduped


def test_weekly_summary_skips_empty_week_and_opt_out(project):
    app, client, calls, state = project
    run = app.extensions['run_reminders']
    assert run(at(2026, 10, 25, 20))['weekly'] == 0          # not opted in
    client.put('/api/notifications', json={'daily_enabled': False, 'daily_hour': 20, 'debt_enabled': True,
        'debt_days_before': 1, 'weekly_enabled': True}, headers=headers())
    assert run(at(2026, 10, 25, 20))['weekly'] == 0          # opted in but nothing logged


def test_feed_requires_auth_and_is_empty_for_new_user(project):
    app, client, calls, state = project
    assert client.get('/api/notifications/feed').status_code == 401
    feed = client.get('/api/notifications/feed', headers=headers()).json
    assert [i for i in feed['items'] if i['type'] != 'nolog'] == []


def test_feed_collects_budget_debt_bill_and_goal_alerts(project):
    app, client, calls, state = project
    today = datetime.now(TZ).date()
    month = today.strftime('%Y-%m')
    assert client.put('/api/budget', json={'month': month, 'currency': 'USD', 'amount': '100'},
                      headers=headers()).status_code == 200
    client.post('/api/transactions', json={'kind': 'expense', 'amount': '85', 'currency': 'USD',
        'category': 'food', 'account': 'cash', 'note': 'x', 'day': today.isoformat(),
        'request_id': 'feed-budget-1'}, headers=headers())
    add_debt(client, (today - timedelta(days=2)).isoformat(), person='Dara')
    bill(client, day_of_month=today.day, remind_days=1)
    from sqlalchemy import update
    from app import personal_tables
    with app.extensions['engine'].begin() as conn:
        conn.execute(update(personal_tables['recurring_items']).values(created_on='2020-01-01'))
    goal = client.post('/api/goals', json={'title': 'Laptop', 'currency': 'USD', 'target': '100',
        'saved': '90', 'request_id': 'feed-goal-0001'}, headers=headers())
    assert goal.status_code == 201, goal.json
    items = client.get('/api/notifications/feed', headers=headers()).json['items']
    types = {i['type'] for i in items}
    assert {'budget', 'debt', 'bill', 'goal'} <= types
    goal_item = next(i for i in items if i['type'] == 'goal')
    assert goal_item['data']['level'] == 80 and goal_item['level'] == 'info'
    budget = next(i for i in items if i['type'] == 'budget')
    assert budget['level'] == 'warn' and budget['data']['currency'] == 'USD'
    debt = next(i for i in items if i['type'] == 'debt')
    assert debt['level'] == 'danger' and debt['data']['days_until'] == -2 and debt['data']['person'] == 'Dara'
    assert next(i for i in items if i['type'] == 'bill')['data']['title'] == 'Rent'
    ids = [i['id'] for i in items]
    assert len(ids) == len(set(ids))
    levels = [i['level'] for i in items]
    assert levels == sorted(levels, key={'danger': 0, 'warn': 1, 'info': 2}.get)
    assert client.get('/api/notifications/feed', headers=headers(OTHER)).json['items'] == [] or all(
        i['type'] == 'nolog' for i in client.get('/api/notifications/feed', headers=headers(OTHER)).json['items'])
