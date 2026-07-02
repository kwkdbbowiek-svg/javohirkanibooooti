import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from database.engine import async_session
from database.crud import get_all_users_ids, add_admin_log
from database.models import User
from states import BroadcastStates
from utils.helpers import is_super_admin

router = Router(name="admin_broadcast")


@router.message(F.text == "📣 Broadcast")
async def broadcast_start(message: Message, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        return

    await message.answer(
        "📣 <b>Xabar tarqatish</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yozing.\n\n"
        "✅ Matn, rasm, video, audio, hujjat yuborishingiz mumkin.\n"
        "❌ Bekor qilish uchun /cancel yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastStates.waiting_for_message)


@router.message(BroadcastStates.waiting_for_message)
async def broadcast_preview(message: Message, state: FSMContext):
    # Save message info
    await state.update_data(
        broadcast_msg_id=message.message_id,
        broadcast_chat_id=message.chat.id
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yuborish", callback_data="confirm_broadcast"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_broadcast")
    )

    await message.answer(
        "👆 Yuqoridagi xabar barcha foydalanuvchilarga yuboriladi.\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BroadcastStates.confirm)


@router.callback_query(F.data == "cancel_broadcast", BroadcastStates.confirm)
async def cancel_broadcast(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Broadcast bekor qilindi.")
    await call.answer()


@router.callback_query(F.data == "confirm_broadcast", BroadcastStates.confirm)
async def do_broadcast(call: CallbackQuery, state: FSMContext, db_user: User, bot: Bot):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    data = await state.get_data()
    msg_id = data.get("broadcast_msg_id")
    chat_id = data.get("broadcast_chat_id")

    await state.clear()
    await call.message.edit_text("⏳ Xabar yuborilmoqda...")
    await call.answer()

    async with async_session() as session:
        user_ids = await get_all_users_ids(session)

    success = 0
    blocked = 0
    total = len(user_ids)

    for i, user_id in enumerate(user_ids):
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=chat_id,
                message_id=msg_id
            )
            success += 1
        except Exception:
            blocked += 1
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)

    async with async_session() as session:
        await add_admin_log(
            session, db_user.tg_id,
            f"Broadcast: {success}/{total} yuborildi, {blocked} blok",
            None, "broadcast"
        )

    await call.message.answer(
        f"✅ <b>Broadcast yakunlandi!</b>\n\n"
        f"📊 Jami: <b>{total}</b> ta\n"
        f"✅ Muvaffaqiyatli: <b>{success}</b> ta\n"
        f"🚫 Bloklaganlar: <b>{blocked}</b> ta",
        parse_mode="HTML"
    )
