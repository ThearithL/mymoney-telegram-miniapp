"""Optional integration check for the quick-entry keypad screen (needs playwright + Chromium)."""
import hashlib,hmac,json,sys,tempfile,time,mimetypes,os
from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import create_app
from playwright.sync_api import sync_playwright

def auth(uid):
    values={'auth_date':str(int(time.time())),'user':json.dumps({'id':uid,'first_name':'Thearith','last_name':'Bou'})}
    secret=hmac.new(b'WebAppData',b'123456:test-token',hashlib.sha256).digest()
    values['hash']=hmac.new(secret,'\n'.join(f'{k}={v}' for k,v in sorted(values.items())).encode(),hashlib.sha256).hexdigest()
    return urlencode(values)

def tap(page,keys):
    for k in keys:
        page.locator(f'#padKeys [data-key="{k}"]').click()

with tempfile.TemporaryDirectory() as temp:
    app=create_app({'TESTING':True,'BOT_TOKEN':'123456:test-token','ADMIN_USER_ID':'123','DATABASE_URL':'sqlite:///'+temp+'/k.db'})
    client=app.test_client()
    mock='window.Telegram={WebApp:{initData:'+json.dumps(auth(123))+',ready(){},expand(){},isVersionAtLeast(){return true},requestFullscreen(){},onEvent(){},BackButton:{onClick(){},show(){},hide(){}}}};'
    with sync_playwright() as p:
        kw={'executable_path':os.environ['CHROMIUM']} if os.environ.get('CHROMIUM') else {}
        browser=p.chromium.launch(headless=True,**kw)
        for width,height in [(360,640),(390,844),(1280,800)]:
            page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce');errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.fulfill(body=mock,content_type='application/javascript'))
            def static(route):
                path=route.request.url.split('https://app.test/',1)[-1].split('?')[0] or 'static/index.html'
                f=ROOT/(path if path!='static/index.html' else 'static/index.html')
                route.fulfill(body=f.read_bytes(),content_type=mimetypes.guess_type(str(f))[0] or 'text/plain')
            page.route('https://app.test/**',static)
            def api(route):
                req=route.request
                url=req.url.split('https://app.test',1)[-1]
                r=client.open(url,method=req.method,data=req.post_data,headers={'Authorization':req.headers.get('authorization',''),'Content-Type':req.headers.get('content-type','application/json')})
                route.fulfill(status=r.status_code,body=r.get_data(),content_type=r.content_type)
            page.route('https://app.test/api/**',api)
            page.goto('https://app.test/')
            page.wait_for_function('state.user && Array.isArray(state.transactions)')
            page.locator('#bootLoader').wait_for(state='hidden')
            base=page.evaluate('state.transactions.length')
            # --- KHR expense with memo chip
            page.locator('#addExpense').click()
            assert page.locator('#padDialog').is_visible()
            assert page.locator('#padSave').is_disabled()
            tap(page,['1','2','00'])
            assert page.locator('#padNum').inner_text()=='1,200',page.locator('#padNum').inner_text()
            tap(page,['0','0','0'])
            assert page.locator('#padNum').inner_text()=='1,200,000'
            tap(page,['back','back'])
            assert page.locator('#padNum').inner_text()=='12,000'
            page.locator('#padMemos .pad-chip',has_text='Coffee').click() if page.evaluate('lang')=='en' else page.locator('#padMemos .pad-chip').nth(3).click()
            page.locator('#padCats .pad-chip').nth(1).click()
            assert not page.locator('#padSave').is_disabled()
            page.locator('#padSave').click()
            page.wait_for_function("!document.getElementById('padDialog').open")
            page.wait_for_function(f'state.transactions.length==={base+1}')
            tx=max(page.evaluate('state.transactions'),key=lambda x:x['id'])
            assert tx['amount']==12000 and tx['currency']=='KHR' and tx['kind']=='expense' and tx['note'],tx
            # --- USD expense with decimals, bank account, want
            page.locator('#addExpense').click()
            page.locator('#padUsd').click()
            assert page.locator('#padSym').inner_text()=='$'
            assert page.locator('#padKeys [data-key="dot"]').inner_text()=='.'
            tap(page,['4','dot','5','0','7'])
            assert page.locator('#padNum').inner_text()=='4.50',page.locator('#padNum').inner_text()
            page.locator('#padAccount').click();page.locator('#padType').click()
            page.locator('#padSave').click()
            page.wait_for_function(f'state.transactions.length==={base+2}')
            usd=max([x for x in page.evaluate('state.transactions') if x['currency']=='USD'],key=lambda x:x['id'])
            assert usd['amount']==450 and usd['account']=='bank' and usd['spending_type']=='want',usd
            # --- income + custom note via Write
            page.locator('#addIncome').click()
            assert page.locator('#padKind').inner_text() in ('Income','ចំណូល')
            tap(page,['5','0','0','00'])
            page.locator('.pad-chip-write').click();page.locator('#padNoteInput').fill('Freelance')
            page.locator('#padSave').click()
            page.wait_for_function(f'state.transactions.length==={base+3}')
            inc=max([x for x in page.evaluate('state.transactions') if x['kind']=='income'],key=lambda x:x['id'])
            assert inc['amount']==50000 and inc['note']=='Freelance',inc
            # --- currency switch drops decimals; more-options carries values to full form
            page.locator('#addExpense').click();page.locator('#padUsd').click();tap(page,['7','dot','2'])
            page.locator('#padKhr').click()
            assert page.locator('#padNum').inner_text()=='7'
            page.locator('#padMore').click()
            assert page.locator('#entryDialog').is_visible() and page.locator('#amount').input_value()=='7'
            page.locator('#closeDialog').click()
            # --- edit still uses full form
            page.evaluate('openEntry("expense",state.transactions[0])')
            assert page.locator('#entryDialog').is_visible() and not page.locator('#padDialog').is_visible()
            page.locator('#closeDialog').click()
            # --- layout: keys and save bar inside viewport
            page.locator('#addExpense').click()
            box=page.locator('#padSave').bounding_box();assert box['y']+box['height']<=height+1,(width,height,box)
            keys=page.locator('#padKeys').bounding_box();assert keys['y']>=0
            assert not page.evaluate('document.getElementById("padDialog").scrollHeight>document.getElementById("padDialog").clientHeight+1'),(width,height,'pad overflows')
            page.screenshot(path=f'/tmp/claude-0/pad_{width}x{height}.png')
            assert not errors,errors
            page.close()
        browser.close()
print('keypad smoke OK')
