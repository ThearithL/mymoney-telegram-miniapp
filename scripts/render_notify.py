"""Send a best-effort Render deployment notice using Render env vars only."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def notify(status: str, detail: str = "") -> bool:
    token = os.getenv("BOT_TOKEN", "").strip()
    admin_id = os.getenv("ADMIN_USER_ID", "").strip()
    if not token or not admin_id.isdecimal() or int(admin_id) <= 0:
        print("Deploy notification skipped: BOT_TOKEN or numeric ADMIN_USER_ID is not configured.")
        return False

    service = os.getenv("RENDER_SERVICE_NAME", "MyMoney")
    commit = os.getenv("RENDER_GIT_COMMIT", "")[:7] or "unknown"
    app_url = os.getenv("APP_URL", "").strip()
    if status == "live":
        text = f"✅ MyMoney is running on Render.\nService: {service}\nCommit: {commit}"
    else:
        text = f"❌ MyMoney deploy startup failed on Render.\nService: {service}\nCommit: {commit}\nStage: {status}"
        if detail:
            text += f"\nDetails: {detail[:300]}"
    if app_url:
        text += f"\nApp: {app_url}"

    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": int(admin_id), "text": text, "disable_web_page_preview": True}).encode()
    request = Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            print("Telegram rejected the deployment notice.", file=sys.stderr)
            return False
        return True
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        print("Could not send deployment notice to Telegram.", file=sys.stderr)
        return False


if __name__ == "__main__":
    notify(os.getenv("DEPLOY_NOTIFY_STATUS", "unknown"), os.getenv("DEPLOY_NOTIFY_DETAIL", ""))
