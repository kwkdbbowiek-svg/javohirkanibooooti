from aiogram import Bot
from database.models import User
from config import SUPER_ADMIN_IDS


def format_money(amount: int) -> str:
    return f"{amount:,} so'm".replace(",", " ")


def is_admin(user: User) -> bool:
    return user.role in ("moderator", "superadmin")


def is_super_admin(user: User) -> bool:
    return user.role == "superadmin" or user.tg_id in SUPER_ADMIN_IDS


async def send_to_all_admins(bot: Bot, admins: list[User], text: str, **kwargs):
    for admin in admins:
        try:
            await bot.send_message(admin.tg_id, text, **kwargs)
        except Exception:
            pass
