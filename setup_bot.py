"""Run once after deployment, or again after changing APP_URL."""
import os
import re
import requests
from dotenv import load_dotenv
load_dotenv()
token = os.environ['BOT_TOKEN']
url = os.environ['APP_URL'].rstrip('/')
secret = os.environ['WEBHOOK_SECRET']
if not url.startswith('https://') or not re.fullmatch(r'[A-Za-z0-9_-]{16,256}', secret):
    raise SystemExit('APP_URL must be HTTPS; WEBHOOK_SECRET needs 16–256 letters/digits/_/-.')
for method, body in [
    ('setWebhook', {'url': url + '/telegram/webhook', 'secret_token': secret, 'allowed_updates': ['message']}),
    ('setChatMenuButton', {'menu_button': {'type': 'web_app', 'text': '💰 MyMoney', 'web_app': {'url': url}}}),
    ('setMyCommands', {'commands': [{'command': 'start', 'description': 'Open MyMoney'}, {'command': 'menu', 'description': 'Show menu'}, {'command': 'id', 'description': 'Show my Telegram ID'}]})
]:
    try:
        response = requests.post(f'https://api.telegram.org/bot{token}/{method}', json=body, timeout=20)
        result = response.json()
    except (requests.RequestException, ValueError):
        raise SystemExit(f'{method} failed. Check network and token.') from None
    if not result.get('ok'):
        raise SystemExit(f"{method}: {result.get('description', 'failed')}")
    print(method + ': OK')
