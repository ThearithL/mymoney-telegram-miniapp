"""Additive personal features; photos are stored in PostgreSQL, not Render's disk."""
import io,json,time,uuid,warnings
from datetime import date,datetime
from zoneinfo import ZoneInfo
from flask import abort,g,request,Response
from sqlalchemy import Table,Column,Integer,BigInteger,String,Text,LargeBinary,UniqueConstraint,select,insert,delete,func
from PIL import Image,ImageOps,UnidentifiedImageError
TZ=ZoneInfo('Asia/Phnom_Penh')

def define_tables(metadata):
    return {
      'trash':Table('transaction_trash',metadata,Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False,index=True),Column('snapshot',Text,nullable=False),Column('request_id',String(64),nullable=False),Column('deleted_at',BigInteger,nullable=False),UniqueConstraint('user_id','request_id')),
      'photos':Table('receipt_photos',metadata,Column('user_id',BigInteger,primary_key=True),Column('request_id',String(64),primary_key=True),Column('data',LargeBinary,nullable=False)),
      'profiles':Table('personal_profiles',metadata,Column('user_id',BigInteger,primary_key=True),Column('name',String(80),nullable=False),Column('bio',String(160),nullable=False)),
      'favorites':Table('expense_favorites',metadata,Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False,index=True),Column('title',String(60),nullable=False),Column('kind',String(10),nullable=False),Column('category',String(20),nullable=False),Column('amount',BigInteger,nullable=False),Column('currency',String(3),nullable=False),Column('account',String(20),nullable=False),Column('note',String(300),nullable=False)),
      'category_budgets':Table('category_budgets',metadata,Column('id',Integer,primary_key=True),Column('user_id',BigInteger,nullable=False),Column('month',String(7),nullable=False),Column('currency',String(3),nullable=False),Column('category',String(20),nullable=False),Column('amount',BigInteger,nullable=False),UniqueConstraint('user_id','month','currency','category'))}

def archive_rows(conn,rows,tables):
    for row in rows:
        data=dict(row);data['day']=data['day'].isoformat()
        conn.execute(insert(tables['trash']).values(user_id=data['user_id'],snapshot=json.dumps(data),request_id=data['request_id'],deleted_at=int(time.time())))

def register_features(app,engine,transactions,tables,auth,json_body,amount_units,month_value,categories):
    trash,photos,profiles,limits,favorites=(tables[k] for k in ['trash','photos','profiles','category_budgets','favorites'])
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

    @app.get('/api/favorites')
    @auth
    def favorites_get():
        with engine.connect() as conn:rows=conn.execute(select(favorites).where(favorites.c.user_id==g.user['id']).order_by(favorites.c.id.desc())).mappings().all()
        return {'favorites':[dict(r) for r in rows]}

    @app.post('/api/favorites')
    @auth
    def favorites_add():
        body=json_body();title=body.get('title');kind=body.get('kind');category=body.get('category');account=body.get('account');note=body.get('note','');currency=body.get('currency')
        if not isinstance(title,str) or not title.strip() or len(title.strip())>60 or kind not in ('expense','income') or category not in categories or account not in ('cash','bank') or not isinstance(note,str) or len(note)>300:abort(400,'Check favorite details.')
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
        if category not in categories or category=='salary':abort(400,'Choose an expense category')
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
