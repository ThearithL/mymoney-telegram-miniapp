"""Shared, currency-separated budget calculations for the Mini App and bot."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, func


def budget_snapshot(engine, transactions, budgets, uid, month, today):
    start = date.fromisoformat(month + '-01')
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    previous = (start - timedelta(days=1)).replace(day=1)
    current = start <= today < end
    days_left = (end - today).days if current else None
    with engine.connect() as conn:
        rows = conn.execute(select(transactions.c.currency, transactions.c.kind,
            func.sum(transactions.c.amount)).where(transactions.c.user_id == uid,
            transactions.c.day >= start, transactions.c.day < end)
            .group_by(transactions.c.currency, transactions.c.kind)).all()
        limits = dict(conn.execute(select(budgets.c.currency, budgets.c.amount).where(
            budgets.c.user_id == uid, budgets.c.month == month)).all())
        prior = dict(conn.execute(select(transactions.c.currency, func.sum(transactions.c.amount))
            .where(transactions.c.user_id == uid, transactions.c.kind == 'expense',
                   transactions.c.day >= previous, transactions.c.day < start)
            .group_by(transactions.c.currency)).all())
    totals = {(currency, kind): int(amount) for currency, kind, amount in rows}
    currencies = []
    for currency in ('KHR', 'USD'):
        spent = totals.get((currency, 'expense'), 0)
        income = totals.get((currency, 'income'), 0)
        limit = limits.get(currency)
        remaining = None if limit is None else limit - spent
        percent = None if not limit else format(
            (Decimal(spent) * 100 / limit).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f')
        status = ('unset' if limit is None else 'over' if spent > limit else
                  'reached' if spent == limit else 'warning' if spent * 100 >= limit * 80 else 'within')
        currencies.append(dict(currency=currency, income=income, expense=spent, net=income-spent,
            budget=limit, remaining=remaining, overspent=max(0, -(remaining or 0)),
            used_percent=percent, status=status,
            daily_allowance=max(0, remaining) // days_left if current and remaining is not None else None,
            previous_month_expense=int(prior.get(currency, 0)),
            expense_change=spent-int(prior.get(currency, 0))))
    return dict(month=month, today=today.isoformat(), previous_month=previous.strftime('%Y-%m'),
                days_left=days_left, is_current_month=current, currencies=currencies,
                amount_units={'USD': 'cents', 'KHR': 'riel'})


def budget_message(snapshot, money):
    lines = ['📊 ស្ថានភាពថវិកា / Budget status', snapshot['month']]
    for row in snapshot['currencies']:
        cur = row['currency']
        lines += ['', cur, f"ចំណាយ / Spent: {money(row['expense'], cur)}"]
        if row['budget'] is None:
            lines += ['មិនទាន់កំណត់ថវិកា / No budget set']
            continue
        lines += [f"ថវិកា / Budget: {money(row['budget'], cur)}"]
        if row['used_percent'] is not None:
            lines += [f"បានប្រើ / Used: {row['used_percent']}%"]
        else:
            lines += ['ថវិកាសូន្យ / Zero budget · percentage unavailable']
        label, amount = ('លើសថវិកា / Over budget', row['overspent']) if row['overspent'] else ('នៅសល់ / Remaining', row['remaining'])
        lines += [f'{label}: {money(amount, cur)}']
        if row['daily_allowance'] is not None:
            lines += [f"ថ្ងៃនេះអាចចាយ / Daily allowance: {money(row['daily_allowance'], cur)}"]
    if snapshot['days_left'] is not None:
        lines += ['', f"Days left including today / រាប់ទាំងថ្ងៃនេះ: {snapshot['days_left']}"]
    return '\n'.join(lines)
