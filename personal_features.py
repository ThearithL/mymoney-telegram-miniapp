"""Additive personal features; photos are stored in PostgreSQL, not Render's disk."""
import io,json,time,uuid,warnings
from datetime import date,datetime
from zoneinfo import ZoneInfo
from flask import abort,g,request,Response
from sqlalchemy import Table,Column,Integer,BigInteger,String,Text,LargeBinary,Numeric,Date,UniqueConstraint,select,insert,delete,update,func
from PIL import Image,ImageOps,UnidentifiedImageError
TZ=ZoneInfo('Asia/Phnom_Penh')

def define_tables(metadata):
    return {
      'trash':Table('transaction_trash',metadata,Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False,index=True),Column('snapshot',Text,nullable=False),Column('request_id',String(64),nullable=False),Column('deleted_at',BigInteger,nullable=False),UniqueConstraint('user_id','request_id')),
      'photos':Table('receipt_photos',metadata,Column('user_id',BigInteger,primary_key=True),Column('request_id',String(64),primary_key=True),Column('data',LargeBinary,nullable=False)),
      'profiles':Table('personal_profiles',metadata,Column('user_id',BigInteger,primary_key=True),Column('name',String(80),nullable=False),Column('bio',String(160),nullable=False)),
      'fx':Table('currency_display_settings',metadata,Column('user_id',BigInteger,primary_key=True),Column('base_currency',String(3),nullable=False),Column('rate_khr_per_usd',Numeric(12,4),nullable=False)),
      'custom_categories':Table('custom_categories',metadata,Column('user_id',BigInteger,primary_key=True),Column('key',String(20),primary_key=True),Column('name',String(40),nullable=False),Column('kind',String(10),nullable=False)),
      'debts':Table('personal_debts',metadata,Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False,index=True),Column('direction',String(8),nullable=False),Column('person',String(80),nullable=False),Column('amount',BigInteger,nullable=False),Column('currency',String(3),nullable=False),Column('note',String(300),nullable=False),Column('due_date',Date,nullable=True),Column('created_at',Date,nullable=False),Column('status',String(10),nullable=False),Column('settled_at',Date,nullable=True)),
      'debt_photos':Table('personal_debt_photos',metadata,Column('debt_id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False),Column('data',LargeBinary,nullable=False)),
      'debt_events':Table('personal_debt_history',metadata,Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False,index=True),Column('debt_id',Integer,nullable=False,index=True),Column('action',String(20),nullable=False),Column('details',Text,nullable=False),Column('created_at',BigInteger,nullable=False)),
      'debt_payments':Table('personal_debt_payments',metadata,Column('id',Integer,primary_key=True),Column('debt_id',Integer,nullable=False,index=True),Column('user_id',BigInteger,nullable=False,index=True),Column('amount',BigInteger,nullable=False),Column('paid_on',Date,nullable=False),Column('note',String(300),nullable=False),Column('created_at',BigInteger,nullable=False)),
      'favorites':Table('expense_favorites',metadata,Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False,index=True),Column('title',String(60),nullable=False),Column('kind',String(10),nullable=False),Column('category',String(20),nullable=False),Column('amount',BigInteger,nullable=False),Column('currency',String(3),nullable=False),Column('account',String(20),nullable=False),Column('note',String(300),nullable=False)),
      'category_budgets':Table('category_budgets',metadata,Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False),Column('month',String(7),nullable=False),Column('currency',String(3),nullable=False),Column('category',String(20),nullable=False),Column('amount',BigInteger,nullable=False),UniqueConstraint('user_id','month','currency','category'))}

def archive_rows(conn,rows,tables):
    for row in rows:
        data=dict(row);data['day']=data['day'].isoformat()
        conn.execute(insert(tables['trash']).values(user_id=data['user_id'],snapshot=json.dumps(data),request_id=data['request_id'],deleted_at=int(time.time())))

def register_features(app,engine,transactions,tables,auth,json_body,amount_units,month_value,categories):
    trash,photos,profiles,limits,favorites,fx,custom_categories,debts,debt_photos,debt_events,debt_payments=(tables[k] for k in ['trash','photos','profiles','category_budgets','favorites','fx','custom_categories','debts','debt_photos','debt_events','debt_payments'])
    def category_allowed(key,kind=None):
        if not isinstance(key,str):return False
        if key in categories:
            if kind is None:return True
            if key=='salary':return kind=='income'
            if key=='other':return kind in ('expense','income')
            return kind=='expense'
        with engine.connect() as conn:row=conn.execute(select(custom_categories.c.kind).where(custom_categories.c.user_id==g.user['id'],custom_categories.c.key==key)).scalar_one_or_none()
        return row is not None and (kind is None or row in (kind,'both'))
    def upsert(table):
        if engine.dialect.name=='postgresql':
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        return dialect_insert(table)
    def owned_entry(conn,identity):
        row=conn.execute(select(transactions).where(transactions.c.id==identity,transactions.c.user_id==g.user['id'])).mappings().first()
        if row is None:abort(404,'Entry not found')
        return row

    @app.get('/api/profile')
    @auth
    def profile_get():
        with engine.connect() as conn:row=conn.execute(select(profiles).where(profiles.c.user_id==g.user['id'])).mappings().first()
        return {'name':row['name'] if row else '', 'bio':row['bio'] if row else '', 'id':g.user['id']}

    @app.put('/api/profile')
    @auth
    def profile_put():
        body=json_body();name=body.get('name');bio=body.get('bio','')
        if not isinstance(name,str) or not 1<=len(name.strip())<=80 or not isinstance(bio,str) or len(bio)>160:abort(400,'Name: 1–80 characters; bio: up to 160.')
        values={'user_id':g.user['id'],'name':name.strip(),'bio':bio.strip()}
        with engine.begin() as conn:conn.execute(upsert(profiles).values(**values).on_conflict_do_update(index_elements=['user_id'],set_={'name':values['name'],'bio':values['bio']}))
        return {'ok':True}

    @app.get('/api/categories')
    @auth
    def categories_get():
        with engine.connect() as conn:rows=conn.execute(select(custom_categories).where(custom_categories.c.user_id==g.user['id']).order_by(custom_categories.c.name)).mappings().all()
        return {'categories':[{'key':r['key'],'name':r['name'],'kind':r['kind']} for r in rows]}

    @app.post('/api/categories')
    @auth
    def categories_add():
        body=json_body();name=body.get('name');kind=body.get('kind')
        if not isinstance(name,str) or not 1<=len(name.strip())<=40 or kind not in ('expense','income','both'):abort(400,'Enter a category name up to 40 characters and choose its type.')
        name=name.strip()
        with engine.begin() as conn:
            count=conn.execute(select(func.count()).select_from(custom_categories).where(custom_categories.c.user_id==g.user['id'])).scalar_one()
            duplicate=conn.execute(select(custom_categories.c.key).where(custom_categories.c.user_id==g.user['id'],func.lower(custom_categories.c.name)==name.lower())).first()
            if count>=40:abort(409,'You can create up to 40 custom categories.')
            if duplicate:abort(409,'A category with that name already exists.')
            key='c_'+uuid.uuid4().hex[:14]
            conn.execute(insert(custom_categories).values(user_id=g.user['id'],key=key,name=name,kind=kind))
        return {'key':key,'name':name,'kind':kind},201

    @app.put('/api/categories/<key>')
    @auth
    def categories_rename(key):
        body=json_body();name=body.get('name')
        if not isinstance(name,str) or not 1<=len(name.strip())<=40:abort(400,'Enter a category name up to 40 characters.')
        name=name.strip()
        with engine.begin() as conn:
            row=conn.execute(select(custom_categories.c.key).where(custom_categories.c.user_id==g.user['id'],custom_categories.c.key==key)).first()
            duplicate=conn.execute(select(custom_categories.c.key).where(custom_categories.c.user_id==g.user['id'],func.lower(custom_categories.c.name)==name.lower(),custom_categories.c.key!=key)).first()
            if row is None:abort(404,'Category not found.')
            if duplicate:abort(409,'A category with that name already exists.')
            conn.execute(custom_categories.update().where(custom_categories.c.user_id==g.user['id'],custom_categories.c.key==key).values(name=name))
        return {'ok':True,'key':key,'name':name}

    @app.delete('/api/categories/<key>')
    @auth
    def categories_remove(key):
        with engine.begin() as conn:
            row=conn.execute(select(custom_categories).where(custom_categories.c.user_id==g.user['id'],custom_categories.c.key==key)).mappings().first()
            if row is None:abort(404,'Category not found.')
            references=sum(conn.execute(select(func.count()).select_from(table).where(table.c.user_id==g.user['id'],table.c.category==key)).scalar_one() for table in (transactions,limits,favorites))
            archived=conn.execute(select(trash.c.snapshot).where(trash.c.user_id==g.user['id'])).scalars().all()
            references+=sum(1 for snapshot in archived if json.loads(snapshot).get('category')==key)
            if references:abort(409,'This category is used by saved entries, budgets, favorites or trash. Rename it instead to keep that history.')
            conn.execute(delete(custom_categories).where(custom_categories.c.user_id==g.user['id'],custom_categories.c.key==key))
        return {'ok':True}

    @app.get('/api/trash')
    @auth
    def trash_get():
        try:offset=max(0,int(request.args.get('offset','0')))
        except ValueError:abort(400,'Invalid offset')
        with engine.connect() as conn:
            rows=conn.execute(select(trash).where(trash.c.user_id==g.user['id']).order_by(trash.c.id.desc()).offset(offset).limit(100)).mappings().all()
            total=conn.execute(select(func.count()).select_from(trash).where(trash.c.user_id==g.user['id'])).scalar_one()
        result=[]
        for r in rows:
            data=json.loads(r['snapshot']);result.append({k:data[k] for k in ['kind','amount','currency','category','note','day']}|{'id':r['id'],'deleted_at':r['deleted_at']})
        return {'entries':result,'total':total}

    @app.post('/api/trash/<int:identity>/restore')
    @auth
    def restore(identity):
        with engine.begin() as conn:
            snapshot=conn.execute(delete(trash).where(trash.c.id==identity,trash.c.user_id==g.user['id']).returning(trash.c.snapshot)).scalar_one_or_none()
            if snapshot is None:abort(404,'Trash entry not found or already restored')
            data=json.loads(snapshot);data.pop('id');data['day']=date.fromisoformat(data['day'])
            if conn.execute(select(transactions.c.id).where(transactions.c.user_id==g.user['id'],transactions.c.request_id==data['request_id'])).first():abort(409,'This entry is already active; refresh your history.')
            result=conn.execute(insert(transactions).values(**data))
        return {'id':result.inserted_primary_key[0]}

    @app.delete('/api/trash/<int:identity>')
    @auth
    def purge(identity):
        if json_body().get('confirmation')!='DELETE':abort(400,'Confirmation required')
        with engine.begin() as conn:
            snapshot=conn.execute(delete(trash).where(trash.c.id==identity,trash.c.user_id==g.user['id']).returning(trash.c.snapshot)).scalar_one_or_none()
            if snapshot is None:abort(404,'Trash entry not found')
            data=json.loads(snapshot)
            conn.execute(delete(photos).where(photos.c.user_id==g.user['id'],photos.c.request_id==data['request_id']))
        return {'ok':True}

    @app.get('/api/transactions/<int:identity>/photo')
    @auth
    def get_photo(identity):
        with engine.connect() as conn:
            row=owned_entry(conn,identity)
            data=conn.execute(select(photos.c.data).where(photos.c.user_id==g.user['id'],photos.c.request_id==row['request_id'])).scalar_one_or_none()
        if data is None:abort(404,'No receipt photo')
        return Response(data,mimetype='image/jpeg',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.get('/api/transactions/<int:identity>/qr')
    @auth
    def get_transaction_qr(identity):
        # QR contains a small, self-contained summary, not a payment address or a
        # public URL. Ownership is checked before any record data is encoded.
        with engine.connect() as conn:
            row=owned_entry(conn,identity)
        amount_text=(f"{row['amount']//100}.{row['amount']%100:02d}"
                     if row['currency']=='USD' else str(row['amount']))
        payload={
            'type':'MYMONEY_PERSONAL_RECORD',
            'id':row['id'],
            'kind':row['kind'],
            'amount':amount_text,
            'currency':row['currency'],
            'date':row['day'].isoformat(),
            'category':row['category'],
            'account':row['account'],
        }
        try:
            import qrcode
            image=qrcode.make(json.dumps(payload,separators=(',',':'),ensure_ascii=False))
            output=io.BytesIO();image.save(output,format='PNG')
        except ImportError:
            abort(503,'QR code support is not installed.')
        return Response(output.getvalue(),mimetype='image/png',headers={
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
        })

    @app.put('/api/transactions/<int:identity>/photo')
    @auth
    def put_photo(identity):
        # Authenticate/authorize before decoding; inspect actual image bytes, not MIME claims.
        with engine.connect() as conn:original_key=owned_entry(conn,identity)['request_id']
        raw=request.get_data()
        if not raw or len(raw)>2*1024*1024:abort(400,'Choose a JPEG, PNG or WebP photo up to 2 MB.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as source:
                    if source.format not in ('JPEG','PNG','WEBP') or getattr(source,'is_animated',False) or source.width*source.height>20_000_000:raise ValueError()
                    source.load();photo=ImageOps.exif_transpose(source).convert('RGB');photo.thumbnail((1600,1600))
                    output=io.BytesIO();photo.save(output,format='JPEG',quality=85)
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):abort(400,'Invalid image. Use a non-animated JPEG, PNG or WebP up to 20 megapixels.')
        with engine.begin() as conn:
            row=owned_entry(conn,identity)
            if row['request_id'] != original_key:abort(409,'Entry changed during upload. Reopen the entry.')
            conn.execute(upsert(photos).values(user_id=g.user['id'],request_id=row['request_id'],data=output.getvalue()).on_conflict_do_update(index_elements=['user_id','request_id'],set_={'data':output.getvalue()}))
        return {'ok':True}

    @app.delete('/api/transactions/<int:identity>/photo')
    @auth
    def remove_photo(identity):
        with engine.begin() as conn:
            row=owned_entry(conn,identity);conn.execute(delete(photos).where(photos.c.user_id==g.user['id'],photos.c.request_id==row['request_id']))
        return {'ok':True}

    def debt_fields(body):
        direction=body.get('direction');person=body.get('person');currency=body.get('currency');note=body.get('note','');raw_due=body.get('due_date') or None
        if direction not in ('borrowed','lent') or not isinstance(person,str) or not 1<=len(person.strip())<=80 or not isinstance(note,str) or len(note)>300:abort(400,'Check the person, direction and note (up to 300 characters).')
        due_date=None
        if raw_due is not None:
            try:due_date=date.fromisoformat(raw_due)
            except (TypeError,ValueError):abort(400,'Enter a valid due date.')
            if due_date.year<2000:abort(400,'Enter a valid due date.')
        return {'direction':direction,'person':person.strip(),'amount':amount_units(body.get('amount'),currency),'currency':currency,'note':note.strip(),'due_date':due_date}

    def owned_debt(conn,identity):
        row=conn.execute(select(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id'])).mappings().first()
        if row is None:abort(404,'Debt record not found.')
        return row

    def debt_snapshot(row):
        snapshot=dict(row)
        for field in ('due_date','created_at','settled_at'):
            if snapshot.get(field) is not None:snapshot[field]=snapshot[field].isoformat()
        return snapshot

    def add_debt_event(conn,identity,action,before=None,after=None,changed_fields=None,extra=None):
        details={'before':debt_snapshot(before) if before is not None else None,'after':debt_snapshot(after) if after is not None else None,'changed_fields':changed_fields or []}
        if extra:details.update(extra)
        conn.execute(insert(debt_events).values(user_id=g.user['id'],debt_id=identity,action=action,details=json.dumps(details,ensure_ascii=False),created_at=int(time.time())))

    def payment_fields(body,currency):
        raw_date=body.get('paid_on') or datetime.now(TZ).date().isoformat();note=body.get('note','')
        if not isinstance(note,str) or len(note)>300:abort(400,'Payment note must be 300 characters or less.')
        try:paid_on=date.fromisoformat(raw_date)
        except (TypeError,ValueError):abort(400,'Enter a valid payment date.')
        if paid_on.year<2000:abort(400,'Enter a valid payment date.')
        return {'amount':amount_units(body.get('amount'),currency),'paid_on':paid_on,'note':note.strip()}

    def debt_paid_total(conn,identity,exclude_payment_id=None):
        query=select(func.coalesce(func.sum(debt_payments.c.amount),0)).where(debt_payments.c.debt_id==identity,debt_payments.c.user_id==g.user['id'])
        if exclude_payment_id is not None:query=query.where(debt_payments.c.id!=exclude_payment_id)
        return int(conn.execute(query).scalar_one())

    def serialize_payment(row):
        return {'id':row['id'],'amount':row['amount'],'paid_on':row['paid_on'].isoformat(),'note':row['note'],'created_at':row['created_at']}

    @app.get('/api/debts')
    @auth
    def debts_get():
        status=request.args.get('status','all')
        if status not in ('all','open','settled'):abort(400,'Choose a valid debt filter.')
        query=select(debts).where(debts.c.user_id==g.user['id'])
        if status!='all':query=query.where(debts.c.status==status)
        query=query.order_by(debts.c.status.asc(),debts.c.due_date.asc().nulls_last(),debts.c.created_at.desc(),debts.c.id.desc())
        with engine.connect() as conn:
            rows=conn.execute(query).mappings().all()
            photo_ids=set(conn.execute(select(debt_photos.c.debt_id).where(debt_photos.c.user_id==g.user['id'])).scalars().all())
            debt_ids=[row['id'] for row in rows]
            payment_rows=conn.execute(select(debt_payments).where(debt_payments.c.user_id==g.user['id'],debt_payments.c.debt_id.in_(debt_ids)).order_by(debt_payments.c.paid_on.desc(),debt_payments.c.id.desc())).mappings().all() if debt_ids else []
        payments_by_debt={}
        for payment in payment_rows:payments_by_debt.setdefault(payment['debt_id'],[]).append(serialize_payment(payment))
        result=[]
        for row in rows:
            item=dict(row);item['due_date']=item['due_date'].isoformat() if item['due_date'] else None;item['created_at']=item['created_at'].isoformat();item['settled_at']=item['settled_at'].isoformat() if item['settled_at'] else None;item['has_photo']=item['id'] in photo_ids;item['payments']=payments_by_debt.get(item['id'],[]);item['paid_total']=sum(p['amount'] for p in item['payments']);item['remaining']=max(0,item['amount']-item['paid_total']);result.append(item)
        return {'debts':result}

    @app.post('/api/debts')
    @auth
    def debts_add():
        values=debt_fields(json_body())|{'user_id':g.user['id'],'created_at':datetime.now(TZ).date(),'status':'open','settled_at':None}
        with engine.begin() as conn:
            identity=conn.execute(insert(debts).values(**values)).inserted_primary_key[0]
            add_debt_event(conn,identity,'created',after=values,changed_fields=['direction','person','amount','currency','due_date','note'])
        return {'id':identity},201

    @app.put('/api/debts/<int:identity>')
    @auth
    def debts_update(identity):
        values=debt_fields(json_body())
        with engine.begin() as conn:
            row=owned_debt(conn,identity)
            paid=debt_paid_total(conn,identity)
            if paid and values['currency']!=row['currency']:abort(400,'Currency cannot be changed after repayments are recorded. Delete the repayments first if they were entered by mistake.')
            if values['amount']<paid:abort(400,'Debt amount cannot be lower than the repayments already recorded.')
            before=dict(row);after=before|values;changed=[key for key,value in values.items() if before[key]!=value]
            if paid and values['amount']==paid and before['status']!='settled':after.update(status='settled',settled_at=datetime.now(TZ).date());changed.extend(['status','settled_at'])
            elif paid and values['amount']>paid and before['status']=='settled':after.update(status='open',settled_at=None);changed.extend(['status','settled_at'])
            if changed:
                conn.execute(update(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id']).values(**{key:after[key] for key in changed}))
                add_debt_event(conn,identity,'updated',before=before,after=after,changed_fields=changed)
        return {'id':identity,'status':row['status']}

    @app.put('/api/debts/<int:identity>/status')
    @auth
    def debts_status(identity):
        status=json_body().get('status')
        if status not in ('open','settled'):abort(400,'Choose open or settled status.')
        with engine.begin() as conn:
            row=owned_debt(conn,identity);before=dict(row);paid=debt_paid_total(conn,identity);remaining=int(row['amount'])-paid
            if status=='settled' and remaining>0:abort(409,'Record repayments until the remaining balance is zero before settling this debt.')
            if status=='open' and remaining==0:abort(409,'This debt is fully repaid. Edit or remove a repayment to reopen its balance.')
            settled_at=datetime.now(TZ).date() if status=='settled' else None
            if before['status']!=status:
                after=before|{'status':status,'settled_at':settled_at}
                conn.execute(update(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id']).values(status=status,settled_at=settled_at))
                add_debt_event(conn,identity,'settled' if status=='settled' else 'reopened',before=before,after=after,changed_fields=['status','settled_at'])
        return {'ok':True,'status':status}

    @app.post('/api/debts/<int:identity>/payments')
    @auth
    def debt_payment_add(identity):
        body=json_body()
        with engine.begin() as conn:
            debt=owned_debt(conn,identity);values=payment_fields(body,debt['currency']);paid=debt_paid_total(conn,identity)
            if values['amount']>int(debt['amount'])-paid:abort(400,'Payment cannot exceed the remaining balance.')
            now=int(time.time());payment_id=conn.execute(insert(debt_payments).values(debt_id=identity,user_id=g.user['id'],**values,created_at=now)).inserted_primary_key[0]
            payment_after={'id':payment_id,'amount':values['amount'],'paid_on':values['paid_on'].isoformat(),'note':values['note'],'created_at':now}
            add_debt_event(conn,identity,'payment_added',after=debt,extra={'payment':payment_after})
            new_paid=paid+values['amount'];remaining=int(debt['amount'])-new_paid
            if remaining>0 and debt['status']=='settled':
                conn.execute(update(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id']).values(status='open',settled_at=None))
                add_debt_event(conn,identity,'reopened',before=debt,after=dict(debt)|{'status':'open','settled_at':None},changed_fields=['status','settled_at'],extra={'reason':'repayment_added'})
            elif remaining==0 and debt['status']!='settled':
                settled_at=datetime.now(TZ).date();after=dict(debt)|{'status':'settled','settled_at':settled_at}
                conn.execute(update(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id']).values(status='settled',settled_at=settled_at))
                add_debt_event(conn,identity,'settled',before=debt,after=after,changed_fields=['status','settled_at'])
        return {'ok':True,'id':payment_id,'remaining':remaining},201

    @app.put('/api/debts/<int:identity>/payments/<int:payment_id>')
    @auth
    def debt_payment_update(identity,payment_id):
        body=json_body()
        with engine.begin() as conn:
            debt=owned_debt(conn,identity);payment=conn.execute(select(debt_payments).where(debt_payments.c.id==payment_id,debt_payments.c.debt_id==identity,debt_payments.c.user_id==g.user['id'])).mappings().first()
            if payment is None:abort(404,'Repayment not found.')
            values=payment_fields(body,debt['currency']);paid_without=debt_paid_total(conn,identity,payment_id)
            if values['amount']>int(debt['amount'])-paid_without:abort(400,'Payment cannot exceed the remaining balance.')
            before=dict(payment);changed=[key for key,value in values.items() if before[key]!=value]
            if changed:
                conn.execute(update(debt_payments).where(debt_payments.c.id==payment_id,debt_payments.c.debt_id==identity,debt_payments.c.user_id==g.user['id']).values(**values))
                after=before|values
                add_debt_event(conn,identity,'payment_updated',extra={'payment_before':{**before,'paid_on':before['paid_on'].isoformat()},'payment_after':{**after,'paid_on':after['paid_on'].isoformat()},'changed_fields':changed})
            total=paid_without+values['amount'];remaining=int(debt['amount'])-total
            if remaining>0 and debt['status']=='settled':
                conn.execute(update(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id']).values(status='open',settled_at=None))
                add_debt_event(conn,identity,'reopened',before=debt,after=dict(debt)|{'status':'open','settled_at':None},changed_fields=['status','settled_at'],extra={'reason':'repayment_edited'})
            elif remaining==0 and debt['status']=='open':
                settled_at=datetime.now(TZ).date();conn.execute(update(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id']).values(status='settled',settled_at=settled_at))
                add_debt_event(conn,identity,'settled',before=debt,after=dict(debt)|{'status':'settled','settled_at':settled_at},changed_fields=['status','settled_at'])
        return {'ok':True,'remaining':remaining}

    @app.delete('/api/debts/<int:identity>/payments/<int:payment_id>')
    @auth
    def debt_payment_remove(identity,payment_id):
        with engine.begin() as conn:
            debt=owned_debt(conn,identity);payment=conn.execute(select(debt_payments).where(debt_payments.c.id==payment_id,debt_payments.c.debt_id==identity,debt_payments.c.user_id==g.user['id'])).mappings().first()
            if payment is None:abort(404,'Repayment not found.')
            before=dict(payment);conn.execute(delete(debt_payments).where(debt_payments.c.id==payment_id,debt_payments.c.debt_id==identity,debt_payments.c.user_id==g.user['id']))
            add_debt_event(conn,identity,'payment_deleted',extra={'payment':{**before,'paid_on':before['paid_on'].isoformat()}})
            remaining=int(debt['amount'])-debt_paid_total(conn,identity)
            if remaining>0 and debt['status']=='settled':
                conn.execute(update(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id']).values(status='open',settled_at=None))
                add_debt_event(conn,identity,'reopened',before=debt,after=dict(debt)|{'status':'open','settled_at':None},changed_fields=['status','settled_at'],extra={'reason':'repayment_deleted'})
        return {'ok':True,'remaining':remaining}

    @app.delete('/api/debts/<int:identity>')
    @auth
    def debts_remove(identity):
        with engine.begin() as conn:
            owned_debt(conn,identity)
            conn.execute(delete(debt_photos).where(debt_photos.c.debt_id==identity,debt_photos.c.user_id==g.user['id']))
            conn.execute(delete(debt_events).where(debt_events.c.debt_id==identity,debt_events.c.user_id==g.user['id']))
            conn.execute(delete(debt_payments).where(debt_payments.c.debt_id==identity,debt_payments.c.user_id==g.user['id']))
            conn.execute(delete(debts).where(debts.c.id==identity,debts.c.user_id==g.user['id']))
        return {'ok':True}

    @app.get('/api/debts/<int:identity>/history')
    @auth
    def debts_history(identity):
        with engine.connect() as conn:
            owned_debt(conn,identity)
            rows=conn.execute(select(debt_events).where(debt_events.c.debt_id==identity,debt_events.c.user_id==g.user['id']).order_by(debt_events.c.created_at.desc(),debt_events.c.id.desc())).mappings().all()
        return {'events':[{'id':r['id'],'action':r['action'],'details':json.loads(r['details']),'created_at':r['created_at']} for r in rows]}

    @app.get('/api/debts/<int:identity>/photo')
    @auth
    def debt_photo_get(identity):
        with engine.connect() as conn:
            owned_debt(conn,identity)
            data=conn.execute(select(debt_photos.c.data).where(debt_photos.c.debt_id==identity,debt_photos.c.user_id==g.user['id'])).scalar_one_or_none()
        if data is None:abort(404,'No proof photo attached.')
        return Response(data,mimetype='image/jpeg',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.put('/api/debts/<int:identity>/photo')
    @auth
    def debt_photo_put(identity):
        with engine.connect() as conn:owned_debt(conn,identity)
        raw=request.get_data()
        if not raw or len(raw)>2*1024*1024:abort(400,'Choose a JPEG, PNG or WebP image up to 2 MB.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as source:
                    if source.format not in ('JPEG','PNG','WEBP') or getattr(source,'is_animated',False) or source.width*source.height>20_000_000:raise ValueError()
                    source.load();photo=ImageOps.exif_transpose(source).convert('RGB');photo.thumbnail((1600,1600));output=io.BytesIO();photo.save(output,format='JPEG',quality=85)
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):abort(400,'Invalid image. Use a non-animated JPEG, PNG or WebP up to 20 megapixels.')
        with engine.begin() as conn:
            row=owned_debt(conn,identity);data=output.getvalue()
            conn.execute(upsert(debt_photos).values(debt_id=identity,user_id=g.user['id'],data=data).on_conflict_do_update(index_elements=['debt_id'],set_={'user_id':g.user['id'],'data':data}))
            add_debt_event(conn,identity,'photo_attached',after=row,extra={'has_photo':True})
        return {'ok':True}

    @app.delete('/api/debts/<int:identity>/photo')
    @auth
    def debt_photo_remove(identity):
        with engine.begin() as conn:
            row=owned_debt(conn,identity);removed=conn.execute(delete(debt_photos).where(debt_photos.c.debt_id==identity,debt_photos.c.user_id==g.user['id'])).rowcount
            if removed:add_debt_event(conn,identity,'photo_removed',after=row,extra={'has_photo':False})
        return {'ok':True}

    @app.get('/api/fx')
    @auth
    def fx_get():
        with engine.connect() as conn:row=conn.execute(select(fx).where(fx.c.user_id==g.user['id'])).mappings().first()
        return {'base_currency':row['base_currency'] if row else 'KHR','rate_khr_per_usd':float(row['rate_khr_per_usd']) if row else 4000.0}

    @app.put('/api/fx')
    @auth
    def fx_put():
        from decimal import Decimal,DecimalException
        body=json_body();currency=body.get('base_currency');raw=body.get('rate_khr_per_usd')
        if currency not in ('KHR','USD'):abort(400,'Display currency must be KHR or USD.')
        try:
            rate=Decimal(str(raw))
            if not rate.is_finite() or not Decimal('1')<=rate<=Decimal('100000') or rate.as_tuple().exponent < -4:raise ValueError()
        except (DecimalException,TypeError,ValueError):abort(400,'Enter a positive rate up to 4 decimal places.')
        values={'user_id':g.user['id'],'base_currency':currency,'rate_khr_per_usd':rate}
        with engine.begin() as conn:conn.execute(upsert(fx).values(**values).on_conflict_do_update(index_elements=['user_id'],set_={'base_currency':currency,'rate_khr_per_usd':rate}))
        return {'ok':True,'base_currency':currency,'rate_khr_per_usd':float(rate)}

    @app.get('/api/favorites')
    @auth
    def favorites_get():
        with engine.connect() as conn:rows=conn.execute(select(favorites).where(favorites.c.user_id==g.user['id']).order_by(favorites.c.id.desc())).mappings().all()
        return {'favorites':[dict(r) for r in rows]}

    @app.post('/api/favorites')
    @auth
    def favorites_add():
        body=json_body();title=body.get('title');kind=body.get('kind');category=body.get('category');account=body.get('account');note=body.get('note','');currency=body.get('currency')
        if not isinstance(title,str) or not title.strip() or len(title.strip())>60 or kind not in ('expense','income') or not category_allowed(category,kind) or account not in ('cash','bank') or not isinstance(note,str) or len(note)>300:abort(400,'Check favorite details.')
        amount=amount_units(body.get('amount'),currency)
        with engine.begin() as conn:
            count=conn.execute(select(func.count()).select_from(favorites).where(favorites.c.user_id==g.user['id'])).scalar_one()
            if count>=12:abort(409,'You can save up to 12 favorites. Remove one to add another.')
            identity=conn.execute(insert(favorites).values(user_id=g.user['id'],title=title.strip(),kind=kind,category=category,amount=amount,currency=currency,account=account,note=note.strip())).inserted_primary_key[0]
        return {'id':identity},201

    @app.delete('/api/favorites/<int:identity>')
    @auth
    def favorites_remove(identity):
        with engine.begin() as conn:changed=conn.execute(delete(favorites).where(favorites.c.id==identity,favorites.c.user_id==g.user['id'])).rowcount
        if not changed:abort(404,'Favorite not found')
        return {'ok':True}

    @app.get('/api/category-budgets')
    @auth
    def category_get():
        month=month_value(request.args.get('month',''));start=date.fromisoformat(month+'-01');end=date(start.year+(start.month==12),start.month%12+1,1)
        with engine.connect() as conn:
            rows=conn.execute(select(limits).where(limits.c.user_id==g.user['id'],limits.c.month==month)).mappings().all()
            spending=conn.execute(select(transactions.c.category,transactions.c.currency,func.sum(transactions.c.amount)).where(transactions.c.user_id==g.user['id'],transactions.c.kind=='expense',transactions.c.day>=start,transactions.c.day<end).group_by(transactions.c.category,transactions.c.currency)).all()
        spent={(cat,cur):int(n) for cat,cur,n in spending}
        return {'budgets':[{'category':r['category'],'currency':r['currency'],'amount':r['amount'],'spent':spent.get((r['category'],r['currency']),0)} for r in rows]}

    @app.put('/api/category-budgets')
    @auth
    def category_put():
        body=json_body();month=month_value(body.get('month',''));category=body.get('category');currency=body.get('currency')
        if not category_allowed(category,'expense') or category=='salary':abort(400,'Choose an expense category')
        values={'user_id':g.user['id'],'month':month,'category':category,'currency':currency,'amount':amount_units(body.get('amount'),currency)}
        with engine.begin() as conn:conn.execute(upsert(limits).values(**values).on_conflict_do_update(index_elements=['user_id','month','currency','category'],set_={'amount':values['amount']}))
        return {'ok':True}

    @app.delete('/api/category-budgets')
    @auth
    def category_delete():
        body=json_body();month=month_value(body.get('month',''))
        with engine.begin() as conn:conn.execute(delete(limits).where(limits.c.user_id==g.user['id'],limits.c.month==month,limits.c.currency==body.get('currency'),limits.c.category==body.get('category')))
        return {'ok':True}

    @app.get('/api/compare')
    @auth
    def compare():
        month=month_value(request.args.get('month',''));start=date.fromisoformat(month+'-01');end=date(start.year+(start.month==12),start.month%12+1,1)
        previous=date(start.year-(start.month==1),(start.month-2)%12+1,1)
        with engine.connect() as conn:
            rows=conn.execute(select(transactions.c.day,transactions.c.kind,transactions.c.currency,transactions.c.amount).where(transactions.c.user_id==g.user['id'],transactions.c.day>=previous,transactions.c.day<end)).all()
        totals={period:{currency:{'income':0,'expense':0} for currency in ['KHR','USD']} for period in ['current','previous']}
        for day,kind,currency,amount in rows:totals['current' if day>=start else 'previous'][currency][kind]+=amount
        return {'month':month,'previous_month':previous.strftime('%Y-%m'),'partial':start<=datetime.now(TZ).date()<end,'totals':totals}
