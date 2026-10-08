"""Run Render startup and report outcome after the configured health route responds."""

import os
import signal
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from render_notify import notify


def fail(stage: str, detail: str) -> int:
    notify(stage, detail)
    return 1


def main() -> int:
    setup = subprocess.run([sys.executable, "setup_bot.py"], check=False)
    if setup.returncode:
        return fail("setup_bot.py", f"process exited with code {setup.returncode}")

    port = os.getenv("PORT", "10000")
    command = [
        sys.executable, "-m", "gunicorn", "wsgi:app",
        "--bind", f"0.0.0.0:{port}", "--workers", "1", "--threads", "4", "--timeout", "60",
    ]
    try:
        server = subprocess.Popen(command)
    except OSError as exc:
        return fail("gunicorn launch", str(exc))

    stopping = False

    def stop_server(_signum, _frame):
        nonlocal stopping
        stopping = True
        if server.poll() is None:
            server.terminate()

    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)

    health_url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline and not stopping:
        exit_code = server.poll()
        if exit_code is not None:
            return fail("health check", f"web process exited with code {exit_code} before becoming healthy")
        try:
            with urlopen(health_url, timeout=3) as response:
                if response.status == 200:
                    notify("live")
                    return server.wait()
        except (HTTPError, URLError, TimeoutError, OSError):
            pass
        time.sleep(2)

    if stopping:
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        return 0

    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
    return fail("health check timeout", "Render app did not return HTTP 200 from /health within 180 seconds")


if __name__ == "__main__":
    raise SystemExit(main())
