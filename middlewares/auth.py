from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.engine import async_session
from database.models import User
from config import SUPER_ADMIN_IDS

# Faqat foydalanuvchilar uchun tugmalar
USER_ONLY_TEXTS = {
    "📚 Kursni sotib olish",
    "ℹ️ Kurs haqida (FAQ)",
    "🎓 Mening kurslarim",
    "👥 Referal tizim",
}

# Faqat adminlar uchun tugmalar
ADMIN_ONLY_TEXTS = {
    "📊 Statistika", "✅ To'lovlar", "💸 Yechish so'rovlari",
    "📚 Kurslar", "💳 Kartalar", "🎁 Chegirmalar",
    "📢 Homiy kanallar", "📣 Broadcast", "👮 Adminlar", "⚙️ Sozlamalar",
}


class UserData:
    """Session yopilgandan keyin ham xavfsiz ishlash uchun oddiy data class"""
    __slots__ = ("tg_id", "username", "full_name", "role",
                 "is_blocked", "balance", "withdrawn", "referer_id",
                 "registered_at")

    def __init__(self, user: User):
        self.tg_id        = user.tg_id
        self.username     = user.username
        self.full_name    = user.full_name
        self.role         = user.role
        self.is_blocked   = user.is_blocked
        self.balance      = user.balance
        self.withdrawn    = user.withdrawn
        self.referer_id   = user.referer_id
        self.registered_at = user.registered_at


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        from database.crud import get_or_create_user, set_user_role

        if isinstance(event, (Message, CallbackQuery)):
            tg_user = event.from_user
        else:
            return await handler(event, data)

        if tg_user is None:
            return await handler(event, data)

        # /start dan referal ID olish
        referer_id = None
        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            parts = event.text.split()
            if len(parts) > 1 and parts[1].startswith("REF_"):
                try:
                    ref_id = int(parts[1].replace("REF_", ""))
                    if ref_id != tg_user.id:
                        referer_id = ref_id
                except ValueError:
                    pass

        # DB dan user olish va barcha kerakli qiymatlarni session ichida o'qish
        async with async_session() as session:
            user, is_new = await get_or_create_user(
                session=session,
                tg_id=tg_user.id,
                username=tg_user.username,
                full_name=tg_user.full_name,
                referer_id=referer_id
            )
            # .env da ko'rsatilgan IDlarga superadmin berish
            if tg_user.id in SUPER_ADMIN_IDS and user.role != "superadmin":
                await set_user_role(session, tg_user.id, "superadmin")
                user.role = "superadmin"

            # Barcha qiymatlarni session ichida o'qib olamiz
            user_data = UserData(user)

        # Session yopildi — endi faqat user_data ishlatamiz

        # Bloklangan foydalanuvchi
        if user_data.is_blocked:
            if isinstance(event, Message):
                await event.answer(
                    "🚫 Siz botdan bloklangansiz. Murojaat: @support"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Bloklangansiz!", show_alert=True)
            return

        # Rol tekshiruvi — faqat Message va faqat tugma matnlari uchun
        if isinstance(event, Message) and event.text:
            is_admin_user = user_data.role in ("moderator", "superadmin")
            txt = event.text

            # Admin user tugmalarini bosdi
            if is_admin_user and txt in USER_ONLY_TEXTS:
                await event.answer(
                    "⚠️ Siz admin sifatida kirgansiz.\n"
                    "Foydalanuvchi menyusiga kirish uchun boshqa akkaunt ishlating."
                )
                return

            # Oddiy user admin tugmalarini bosdi — jim o'tkazamiz
            if not is_admin_user and txt in ADMIN_ONLY_TEXTS:
                return

        data["db_user"]    = user_data
        data["is_new_user"] = is_new
        return await handler(event, data)
