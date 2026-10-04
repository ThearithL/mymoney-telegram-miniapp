"""Optional integration check: install playwright==1.51.0 and its Chromium browser."""
import hashlib,hmac,json,sys,tempfile,threading,time,uuid,io
from PIL import Image
from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from werkzeug.serving import make_server,WSGIRequestHandler
from playwright.sync_api import sync_playwright
class Quiet(WSGIRequestHandler):
    def log_request(self,*args): pass

def wait_state(page, expression):
    for _ in range(100):
        if page.evaluate(expression): return
        page.wait_for_timeout(50)
    raise AssertionError({'expression':expression,'url':page.url,'errors':page.locator('body').inner_text()[-1500:]})

def auth(uid):
    values={'auth_date':str(int(time.time())),'user':json.dumps({'id':uid,'first_name':'Thearith'})}
    secret=hmac.new(b'WebAppData',b'123456:test-token',hashlib.sha256).digest()
    values['hash']=hmac.new(secret,'\n'.join(f'{k}={v}' for k,v in sorted(values.items())).encode(),hashlib.sha256).hexdigest()
    return urlencode(values)

with tempfile.TemporaryDirectory() as temp:
    app=create_app({'TESTING':True,'BOT_TOKEN':'123456:test-token','ADMIN_USER_ID':'123','ALLOWED_USER_IDS':'456','DATABASE_URL':'sqlite:///'+temp+'/ui.db'})
    client=app.test_client();today=datetime.now(ZoneInfo('Asia/Phnom_Penh')).date().isoformat()
    def add(category,amount,uid=123):
        response=client.post('/api/transactions',headers={'Authorization':'tma '+auth(uid)},json={'kind':'expense','currency':'KHR','amount':amount,'category':category,'account':'cash','day':today,'note':'Demo '+category,'request_id':uuid.uuid4().hex})
        assert response.status_code==201
    add('food','9000',456)
    server=make_server('127.0.0.1',0,app,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
    mock='window.Telegram={WebApp:{initData:'+json.dumps(auth(123))+',ready(){},expand(){},isVersionAtLeast(){return true},requestFullscreen(){},onEvent(){},BackButton:{onClick(){},show(){},hide(){}}}};'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for width,height in [(320,568),(360,800),(390,844),(768,1024),(844,390),(1280,800),(1920,1080)]:
                add('food','12000');add('coffee','6000')
                page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce');errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.route('https://telegram.org/js/telegram-web-app.js',lambda r:r.fulfill(body=mock,content_type='application/javascript'))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                wait_state(page, '() => state.user && state.transactions.length === 2')
                page.locator('#bootLoader').wait_for(state='hidden')
                assert page.locator('#openCalculator').count()==0
                for language in ['km','en']:
                    page.evaluate('(v)=>{lang=v;translate()}',language)
                    for name in ['home','history','reports','goals','settings']:
                        page.locator('[data-page="'+name+'"]').click()
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),(width,name)
                    page.locator('#theme').select_option('dark' if language=='km' else 'light')
                page.locator('[data-page="reports"]').click()
                assert '66.7%' in page.locator('#donutPanel').inner_text()
                assert '33.3%' in page.locator('#donutPanel').inner_text()
                if width==1280: page.screenshot(path='/tmp/mymoney-reports-latest.png',full_page=True)
                page.locator('[data-page="history"]').click()
                page.locator('#historyList .row').first.click()
                if width==320:
                    image=io.BytesIO();Image.new('RGB',(50,40),'green').save(image,format='PNG')
                    page.locator('#photoFile').set_input_files({'name':'receipt.png','mimeType':'image/png','buffer':image.getvalue()})
                    page.locator('#uploadPhoto').click()
                    wait_state(page,'() => document.getElementById("receiptPhoto").naturalWidth > 0')
                page.locator('#editReceipt').click()
                page.locator('#amount').fill('18000');page.locator('#saveEntry').click()
                wait_state(page, '() => !document.getElementById("entryDialog").open && state.transactions.some(r=>r.amount===18000)')
                page.locator('#toggleSelect').click();page.locator('#historyList input[type=checkbox]').first.check()
                page.locator('#deleteSelected').click();page.locator('#bulkDialog').wait_for(state='visible')
                assert page.locator('#confirmBulk').is_disabled()
                page.locator('#cancelBulk').click();assert page.locator('#historyList input:checked').count()==1
                page.locator('#deleteSelected').click();page.locator('#deletePhrase').fill('DELETE');page.locator('#confirmBulk').click()
                wait_state(page, '() => !document.getElementById("bulkDialog").open && state.transactions.length===1')
                page.locator('.delete-all-area summary').click();page.locator('#deleteAll').click()
                page.locator('#deletePhrase').fill('DELETE');page.locator('#confirmBulk').click()
                wait_state(page, '() => !document.getElementById("bulkDialog").open && state.transactions.length===0')
                page.locator('[data-page="reports"]').click();assert 'No expenses' in page.locator('#donutPanel').inner_text()
                if width==320:
                    page.locator('[data-page="settings"]').click()
                    page.locator('#profileName').fill('Thearith Personal');page.locator('#profileBio').fill('Student')
                    page.locator('#profileForm button').click()
                    wait_state(page,'() => state.user.name === "Thearith Personal"')
                    page.locator('#openTrash').click()
                    card=page.locator('.trash-card').filter(has_text='Demo coffee')
                    card.locator('button').first.click()
                    wait_state(page,'() => state.transactions.length === 1')
                    page.locator('[data-page="history"]').click();page.locator('#historyList .row').first.click()
                    wait_state(page,'() => document.getElementById("receiptPhoto").naturalWidth > 0')
                    page.locator('#closeReceipt').click()
                    page.locator('[data-page="home"]').click();page.locator('#manageBudget').click()
                    page.locator('#budgetCategory').select_option('coffee');page.locator('#categoryLimit').fill('20000')
                    page.locator('#categoryBudgetForm button').click()
                    wait_state(page,'() => categoryData.some(r=>r.category === "coffee" && r.spent === 18000)')
                    assert '90%' in page.locator('#categoryLimits').inner_text()
                    page.locator('[data-page="reports"]').click()
                    assert page.locator('#comparison').inner_text()
                    active=client.get('/api/data?month='+today[:7],headers={'Authorization':'tma '+auth(123)}).json['transactions']
                    for entry in active:client.delete('/api/transactions/'+str(entry['id']),headers={'Authorization':'tma '+auth(123)})
                assert not errors,errors
                assert len(client.get('/api/data?month='+today[:7],headers={'Authorization':'tma '+auth(456)}).json['transactions'])==1
                print(f'PASS {width}x{height}: languages/themes, navigation, donut, edit, selected/all delete, isolation; no JS errors',flush=True)
                page.close()
            browser.close()
    finally: server.shutdown()
