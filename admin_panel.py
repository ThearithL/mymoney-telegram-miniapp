"""Private Telegram admin panel. All entry points enforce the configured owner ID."""
import time
import uuid
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, insert, update, delete, func, union


def button(text, data):
    return {'text': text, 'callback_data': data}


def panel(text, rows=None):
    return {'text': text, 'reply_markup': {'inline_keyboard': rows or []}}


def money(amount, currency):
    value = Decimal(amount or 0) / (100 if currency == 'USD' else 1)
    return f'{value:,.2f} USD' if currency == 'USD' else f'{value:,.0f} KHR'


class AdminPanel:
    def __init__(self, engine, owner, allowed, tables, telegram, config):
        self.engine, self.owner, self.allowed = engine, owner, allowed
        self.users, self.access, self.tx, self.budgets, self.actions, self.audit, self.goals = tables
        self.telegram, self.config = telegram, config

    def ids(self):
        return union(select(self.users.c.user_id), select(self.access.c.user_id),
                     select(self.tx.c.user_id), select(self.budgets.c.user_id), select(self.goals.c.user_id)).subquery()

    def status(self, uid, stored):
        if uid == self.owner:
            return 'admin'
        if stored:
            return stored
        return 'approved' if uid in self.allowed else 'not_requested'

    def back(self):
        return [button('⬅️ Admin menu', 'admin:home')]

    def render(self, actor, action):
        if not self.owner or actor != self.owner:
            return panel('🔒 Admin only.')
        parts = action.split(':')
        try:
            op = parts[1]
            if op == 'home':
                return panel('🛡 Admin Control\nគ្រប់គ្រងអ្នកប្រើ និងមើលទិន្នន័យ / Manage users and review data', [
                    [button('👥 អ្នកប្រើ / Users', 'admin:users:0'), button('⏳ សំណើ / Requests', 'admin:pending:0')],
                    [button('📊 ស្ថិតិ / Statistics', 'admin:stats'), button('⚙️ ស្ថានភាព / Status', 'admin:system')],
                    [button('🕘 ប្រវត្តិ Admin / Audit', 'admin:audit:0')]])
            if op in ('users', 'pending'):
                return self.user_list(max(0, int(parts[2])), op == 'pending')
            if op == 'user':
                return self.user_detail(int(parts[2]))
            if op == 'tx':
                return self.history(int(parts[2]), max(0, int(parts[3])))
            if op in ('grant', 'revoke'):
                return self.confirm(op, int(parts[2]))
            if op == 'apply':
                return self.apply(parts[2])
            if op == 'goals':
                return self.goal_list(int(parts[2]), max(0,int(parts[3])))
            if op == 'stats':
                return self.stats()
            if op == 'audit':
                return self.audit_list(max(0, int(parts[2])))
            if op == 'system':
                return panel('⚙️ Configuration\n'
                    f'Admin ID: {self.owner}\nDatabase: {self.engine.dialect.name}\n'
                    f"App URL: {self.config['APP_URL']}\n"
                    f"Bot token configured: {bool(self.config['BOT_TOKEN'])}\n"
                    f"Webhook secret configured: {bool(self.config['WEBHOOK_SECRET'])}\n"
                    'Secrets are never displayed. Hosting/token settings are managed in Render.', [self.back()])
        except (ValueError, IndexError):
            pass
        return panel('Invalid or expired admin action.', [self.back()])

    def user_list(self, offset, pending=False):
        ids = self.ids()
        with self.engine.connect() as conn:
            query = select(ids.c.user_id, self.users.c.name, self.access.c.status).select_from(
                ids.outerjoin(self.users, self.users.c.user_id == ids.c.user_id)
                .outerjoin(self.access, self.access.c.user_id == ids.c.user_id))
            if pending:
                query = query.where(self.access.c.status == 'pending')
            rows = conn.execute(query.order_by(ids.c.user_id).offset(offset).limit(9)).mappings().all()
        buttons = [[button(f"{r['user_id']} · {(r['name'] or 'User')[:25]} · {self.status(r['user_id'],r['status'])}",
                           f"admin:user:{r['user_id']}")] for r in rows[:8]]
        mode = 'pending' if pending else 'users'
        pager = []
        if offset:
            pager.append(button('⬅️ Previous', f'admin:{mode}:{max(0,offset-8)}'))
        if len(rows) > 8:
            pager.append(button('Next ➡️', f'admin:{mode}:{offset+8}'))
        if pager:
            buttons.append(pager)
        buttons.append(self.back())
        return panel(('⏳ Pending requests' if pending else '👥 All known users') +
                     (f' · Page {offset//8+1}' if rows else '\nNo users here.'), buttons)

    def user_detail(self, uid):
        ids = self.ids()
        with self.engine.connect() as conn:
            if conn.execute(select(ids.c.user_id).where(ids.c.user_id == uid)).first() is None:
                return panel('User not found.', [self.back()])
            user = conn.execute(select(self.users).where(self.users.c.user_id == uid)).mappings().first()
            access = conn.execute(select(self.access).where(self.access.c.user_id == uid)).mappings().first()
            totals = conn.execute(select(self.tx.c.currency, self.tx.c.kind, func.sum(self.tx.c.amount))
                .where(self.tx.c.user_id == uid).group_by(self.tx.c.currency, self.tx.c.kind)).all()
            month = datetime.now(ZoneInfo('Asia/Phnom_Penh')).strftime('%Y-%m')
            limits = conn.execute(select(self.budgets).where(self.budgets.c.user_id == uid,
                self.budgets.c.month == month)).mappings().all()
        text = f"👤 {(user or {}).get('name','User')}\nTelegram ID: {uid}\nStatus: {self.status(uid, access['status'] if access else None)}\n\nAll-time recorded totals:"
        text += ''.join(f'\n{kind}: {money(amount,currency)}' for currency,kind,amount in totals) or '\nNo transactions.'
        text += f'\n\nBudgets ({month}):' + (''.join(f"\n{money(r['amount'],r['currency'])}" for r in limits) or '\nNone')
        rows = [[button('🧾 កំណត់ត្រា / Transactions', f'admin:tx:{uid}:0')], [button('🎯 Goals', f'admin:goals:{uid}:0')]]
        if uid != self.owner:
            if access and access['status'] == 'pending':
                rows.append([button('✅ Approve', 'approve:'+access['request_key']), button('❌ Reject','reject:'+access['request_key'])])
            rows.append([button('✅ ផ្ដល់សិទ្ធិ / Grant', f'admin:grant:{uid}'), button('🔒 ដកសិទ្ធិ / Revoke', f'admin:revoke:{uid}')])
        rows.extend([[button('⬅️ Users', 'admin:users:0')], self.back()])
        return panel(text, rows)

    def goal_list(self, uid, offset):
        with self.engine.connect() as conn:
            rows=conn.execute(select(self.goals).where(self.goals.c.user_id==uid).order_by(self.goals.c.id).offset(offset).limit(6)).mappings().all()
        text=f'🎯 User {uid} · Savings goals\n'
        for r in rows[:5]:
            text+=f"\n{r['title']}\n{money(r['saved'],r['currency'])} / {money(r['target'],r['currency'])}\n"
        if not rows:
            text+='No goals.'
        pager=[]
        if offset:
            pager.append(button('⬅️ Previous',f'admin:goals:{uid}:{max(0,offset-5)}'))
        if len(rows)>5:
            pager.append(button('Next ➡️',f'admin:goals:{uid}:{offset+5}'))
        return panel(text,([pager] if pager else [])+[[button('⬅️ User',f'admin:user:{uid}')]])

    def history(self, uid, offset):
        with self.engine.connect() as conn:
            rows = conn.execute(select(self.tx).where(self.tx.c.user_id == uid)
                .order_by(self.tx.c.day.desc(),self.tx.c.id.desc()).offset(offset).limit(6)).mappings().all()
        text = f'🧾 User {uid} · Page {offset//5+1}\n'
        for r in rows[:5]:
            text += f"\n#{r['id']} · {r['day']} · {r['kind']}\n{money(r['amount'],r['currency'])} · {r['category']} · {r['account']}\n{r['note']}\n"
        if not rows:
            text += 'No entries.'
        pager = []
        if offset:
            pager.append(button('⬅️ Previous', f'admin:tx:{uid}:{max(0,offset-5)}'))
        if len(rows)>5:
            pager.append(button('Next ➡️', f'admin:tx:{uid}:{offset+5}'))
        return panel(text, ([pager] if pager else []) + [[button('⬅️ User',f'admin:user:{uid}')]])

    def confirm(self, operation, uid):
        if uid == self.owner:
            return panel('Owner access cannot be revoked here.', [self.back()])
        ids = self.ids()
        with self.engine.begin() as conn:
            if conn.execute(select(ids.c.user_id).where(ids.c.user_id == uid)).first() is None:
                return panel('User not found.', [self.back()])
            # Replace prior unconfirmed actions for the target to reject stale buttons.
            conn.execute(delete(self.actions).where(self.actions.c.target_id == uid))
            key = uuid.uuid4().hex
            conn.execute(insert(self.actions).values(key=key, target_id=uid, action=operation,
                expires_at=int(time.time())+300))
        return panel(f'Confirm {operation.upper()} access for user {uid}?\nTransaction data will be retained.\nExpires in 5 minutes.', [
            [button('✅ Confirm', 'admin:apply:'+key), button('Cancel', f'admin:user:{uid}')]])

    def apply(self, key):
        if self.engine.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert
        with self.engine.begin() as conn:
            row = conn.execute(delete(self.actions).where(self.actions.c.key == key,
                self.actions.c.expires_at >= int(time.time())).returning(self.actions)).mappings().first()
            if not row or row['target_id'] == self.owner:
                return panel('Action expired or already used.', [self.back()])
            uid = row['target_id']
            state = 'approved' if row['action'] == 'grant' else 'revoked'
            name = conn.execute(select(self.users.c.name).where(self.users.c.user_id == uid)).scalar() or 'User'
            stmt = upsert(self.access).values(user_id=uid,name=name,status=state,request_key=uuid.uuid4().hex,notified_at=0)
            conn.execute(stmt.on_conflict_do_update(index_elements=['user_id'],set_={'status':state,'request_key':uuid.uuid4().hex}))
            conn.execute(insert(self.audit).values(admin_id=self.owner,target_id=uid,action=row['action'],at=int(time.time())))
        sent = self.telegram('sendMessage', {'chat_id':uid,'text':
            '✅ សិទ្ធិបានអនុញ្ញាត / Access granted. Send /start.' if state=='approved' else
            '🔒 សិទ្ធិត្រូវបានដក / Access revoked. Contact the owner.'})
        result = self.user_detail(uid)
        result['text'] = '✅ Saved.' + ('' if sent else ' User notification failed.') + '\n' + result['text']
        return result

    def stats(self):
        ids = self.ids()
        with self.engine.connect() as conn:
            users = conn.execute(select(func.count()).select_from(ids)).scalar()
            pending = conn.execute(select(func.count()).select_from(self.access).where(self.access.c.status=='pending')).scalar()
            count = conn.execute(select(func.count()).select_from(self.tx)).scalar()
            totals = conn.execute(select(self.tx.c.currency,self.tx.c.kind,func.sum(self.tx.c.amount))
                .group_by(self.tx.c.currency,self.tx.c.kind)).all()
        return panel(f'📊 All-time statistics\nKnown users: {users}\nPending: {pending}\nTransactions: {count}\n' +
                     ''.join(f'\n{kind}: {money(amount,currency)}' for currency,kind,amount in totals), [self.back()])

    def audit_list(self, offset):
        with self.engine.connect() as conn:
            rows = conn.execute(select(self.audit).order_by(self.audit.c.id.desc()).offset(offset).limit(11)).mappings().all()
        text = '🕘 Admin decisions · Phnom Penh time\n'
        for r in rows[:10]:
            stamp = datetime.fromtimestamp(r['at'],ZoneInfo('Asia/Phnom_Penh')).strftime('%Y-%m-%d %H:%M')
            text += f"\n{stamp} · {r['action']} · User {r['target_id']}"
        if not rows:
            text += 'No decisions yet.'
        pager=[]
        if offset:
            pager.append(button('⬅️ Previous',f'admin:audit:{max(0,offset-10)}'))
        if len(rows)>10:
            pager.append(button('Next ➡️',f'admin:audit:{offset+10}'))
        return panel(text,([pager] if pager else [])+[self.back()])
