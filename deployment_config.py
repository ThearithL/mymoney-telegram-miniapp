"""Fail closed when a Vercel deployment lacks persistent storage or authentication."""
import re
from urllib.parse import urlsplit


def validate_vercel_environment(env):
    if env.get("VERCEL") != "1":
        return
    required = ("DATABASE_URL", "BOT_TOKEN", "APP_URL", "WEBHOOK_SECRET", "FLASK_SECRET_KEY", "ADMIN_USER_ID")
    missing = [key for key in required if not env.get(key, "").strip()]
    if missing:
        raise RuntimeError("Missing Vercel environment variables: " + ", ".join(missing))
    if not env["DATABASE_URL"].startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("Vercel requires a persistent PostgreSQL DATABASE_URL; SQLite is not supported.")
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", env["BOT_TOKEN"]):
        raise RuntimeError("BOT_TOKEN format is invalid.")
    parsed = urlsplit(env["APP_URL"])
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise RuntimeError("APP_URL must be the stable HTTPS origin of this deployment.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", env["WEBHOOK_SECRET"]):
        raise RuntimeError("WEBHOOK_SECRET must contain 16-256 letters, numbers, underscores or hyphens.")
    if len(env["FLASK_SECRET_KEY"]) < 32:
        raise RuntimeError("FLASK_SECRET_KEY must contain at least 32 characters.")
    if not env["ADMIN_USER_ID"].isdecimal() or int(env["ADMIN_USER_ID"]) <= 0:
        raise RuntimeError("ADMIN_USER_ID must be a positive Telegram user ID.")
    if not (env.get("ADMIN_PASSWORD_HASH") or env.get("ADMIN_PASSWORD")):
        raise RuntimeError("Set ADMIN_PASSWORD_HASH or ADMIN_PASSWORD for the admin panel.")
