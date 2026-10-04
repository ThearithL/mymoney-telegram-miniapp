"""Register Telegram webhook, Mini App menu and commands using server environment."""
import os
import re
import requests
from dotenv import load_dotenv
load_dotenv()
token = os.environ['BOT_TOKEN'].strip()
url = os.environ['APP_URL'].strip().rstrip('/')
secret = os.environ['WEBHOOK_SECRET'].strip()
admin = os.getenv('ADMIN_USER_ID', '').strip()
if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token):
    raise SystemExit('BOT_TOKEN must be the complete token from BotFather, not a username or user ID.')
if not url.startswith('https://') or not re.fullmatch(r'[A-Za-z0-9_-]{16,256}', secret):
    raise SystemExit('APP_URL must be HTTPS; WEBHOOK_SECRET needs 16–256 letters/digits/_/-.')
if admin and (not admin.isdecimal() or int(admin) <= 0):
    raise SystemExit('ADMIN_USER_ID must be your positive numeric personal Telegram ID, or empty during bootstrap.')

def call(method, body, required=True):
    try:
        result = requests.post(f'https://api.telegram.org/bot{token}/{method}', json=body, timeout=20).json()
    except (requests.RequestException, ValueError):
        if required:
            raise SystemExit(f'{method} failed. Check network and token.') from None
        return False
    if not result.get('ok'):
        if required:
            raise SystemExit(f"{method}: {result.get('description', 'failed')}")
        return False
    print(method + ': OK')
    return True

commands = [
    {'command':'start','description':'Open MyMoney and show buttons'},
    {'command':'menu','description':'Show menu'},
    {'command':'id','description':'Show my Telegram ID'},
    {'command':'request','description':'Request access'},
    {'command':'summary','description':'My income and expense summary'},
    {'command':'help','description':'Help and privacy information'}]
call('getMe', {})
call('setWebhook', {'url':url+'/telegram/webhook','secret_token':secret,'allowed_updates':['message','callback_query']})
call('setChatMenuButton', {'menu_button':{'type':'web_app','text':'MyMoney','web_app':{'url':url}}})
call('setMyCommands', {'commands':commands})
if admin:
    ok = call('setMyCommands', {'scope':{'type':'chat','chat_id':int(admin)},'commands':commands+[
        {'command':'admin','description':'Admin control panel'},
        {'command':'requests','description':'Admin: pending access requests'}]}, required=False)
    if not ok:
        print('Admin scoped commands pending: owner should send /start. The /admin command still works.')
