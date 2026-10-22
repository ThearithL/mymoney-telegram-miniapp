import os
import threading
import time

from app import create_app

app = create_app()


def _reminder_loop(interval=300):
    while True:
        time.sleep(interval)
        try:
            app.extensions['run_reminders']()
        except Exception:
            app.logger.exception('Reminder run failed')


# Optional: also run reminders from inside the web process (every 5 minutes while the
# service is awake). On hosts that sleep idle services, keep an external monitor calling
# /ops/reminders/<REMINDER_SECRET> too. Duplicate sends are impossible either way.
if os.getenv('REMINDER_SCHEDULER') == '1':
    threading.Thread(target=_reminder_loop, daemon=True, name='reminders').start()
