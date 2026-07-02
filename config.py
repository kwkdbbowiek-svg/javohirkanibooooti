import os
from dotenv import load_dotenv

load_dotenv()

# ── Bot token ─────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ── Database ──────────────────────────────────────────────────
# Railway da PostgreSQL plugin qo'shilsa DATABASE_URL o'zi beriladi.
# Lokal uchun SQLite ishlatiladi.
_raw_db = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db")

if _raw_db.startswith("postgres://"):
    _raw_db = _raw_db.replace("postgres://", "postgresql+asyncpg://", 1)
elif _raw_db.startswith("postgresql://") and "+asyncpg" not in _raw_db:
    _raw_db = _raw_db.replace("postgresql://", "postgresql+asyncpg://", 1)

DATABASE_URL: str = _raw_db

# ── Admin IDlar ───────────────────────────────────────────────
_raw_ids = os.getenv("SUPER_ADMIN_IDS", "")
SUPER_ADMIN_IDS: list[int] = [
    int(i.strip()) for i in _raw_ids.split(",") if i.strip().isdigit()
]

# ── Webhook / Railway ────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "8080"))

_raw_webhook_url = os.getenv("WEBHOOK_URL", "").strip()
if not _raw_webhook_url:
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if not railway_domain:
        railway_domain = os.getenv("RAILWAY_STATIC_URL", "").strip()
    if railway_domain:
        _raw_webhook_url = f"https://{railway_domain}"

WEBHOOK_URL: str = _raw_webhook_url.rstrip("/")
WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook").strip()
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")

# ── Referal / Yechish ─────────────────────────────────────────
REFERRAL_BONUS: int = int(os.getenv("REFERRAL_BONUS", "20000"))
MIN_WITHDRAWAL: int = int(os.getenv("MIN_WITHDRAWAL", "50000"))

# ── Cheklar kanali ────────────────────────────────────────────
_rcid = os.getenv("RECEIPTS_CHANNEL_ID", "").strip()
RECEIPTS_CHANNEL_ID: int | None = int(_rcid) if _rcid.lstrip("-").isdigit() else None

