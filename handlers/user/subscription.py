from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from database.engine import async_session
from database.crud import get_sponsor_channels
from keyboards.user_kb import main_menu_kb, subscribe_check_kb

router = Router(name="subscription")


@router.callback_query(F.data == "check_subscription")
async def check_subscription(call: CallbackQuery, bot: Bot):
    async with async_session() as session:
        channels = await get_sponsor_channels(session)

    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, call.from_user.id)
            if member.status in ("left", "kicked", "banned"):
                not_subscribed.append(ch)
        except Exception:
            not_subscribed.append(ch)

    if not_subscribed:
        await call.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        kb = subscribe_check_kb(not_subscribed)
        await call.message.edit_reply_markup(reply_markup=kb)
        return

    await call.message.delete()
    await call.message.answer(
        "✅ <b>Rahmat! Barcha kanallarga a'zo bo'ldingiz.</b>\n\n"
        "Endi botdan to'liq foydalanishingiz mumkin! 🎉",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
