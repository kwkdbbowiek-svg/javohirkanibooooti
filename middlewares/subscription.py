from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.engine import async_session
from database.crud import get_sponsor_channels
from keyboards.user_kb import subscribe_check_kb


BYPASS_CALLBACKS = {"check_subscription"}
BYPASS_COMMANDS = {"/start"}


class SubscriptionMiddleware(BaseMiddleware):
    """
    Checks if user is subscribed to all sponsor channels before allowing access.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        bot: Bot = data.get("bot")
        db_user = data.get("db_user")

        if db_user is None:
            return await handler(event, data)

        # Skip subscription check for admins
        if db_user.role in ("moderator", "superadmin"):
            return await handler(event, data)

        # Skip for bypass callbacks
        if isinstance(event, CallbackQuery) and event.data in BYPASS_CALLBACKS:
            return await handler(event, data)

        async with async_session() as session:
            channels = await get_sponsor_channels(session)

        if not channels:
            return await handler(event, data)

        # Check subscription for each channel
        not_subscribed = []
        for ch in channels:
            try:
                member = await bot.get_chat_member(ch.channel_id, db_user.tg_id)
                if member.status in ("left", "kicked", "banned"):
                    not_subscribed.append(ch)
            except Exception:
                not_subscribed.append(ch)

        if not_subscribed:
            text = (
                "📢 <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>\n\n"
                "A'zo bo'lgandan so'ng <b>✅ Tekshirish</b> tugmasini bosing."
            )
            kb = subscribe_check_kb(not_subscribed)
            if isinstance(event, Message):
                await event.answer(text, reply_markup=kb, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
                await event.answer()
            return

        return await handler(event, data)
