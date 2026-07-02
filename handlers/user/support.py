from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.engine import async_session
from database.crud import create_support_ticket, get_admins, close_ticket
from database.models import User
from keyboards.admin_kb import support_reply_kb
from keyboards.user_kb import main_menu_kb
from states import SupportStates
from utils.helpers import is_admin

router = Router(name="support")


@router.message(F.text == "📞 Qo'llab-quvvatlash")
async def support_start(message: Message, state: FSMContext, db_user: User):
    # Faqat oddiy foydalanuvchilar uchun
    if db_user.role != "user":
        return

    await message.answer(
        "📞 <b>Admin bilan bog'lanish</b>\n\n"
        "Savolingizni yoki muammongizni yozing.\n"
        "Admin imkon qadar tez javob beradi!\n\n"
        "❌ Bekor qilish uchun /cancel yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(SupportStates.waiting_for_message)


@router.message(SupportStates.waiting_for_message)
async def process_support_message(message: Message, state: FSMContext, db_user: User, bot: Bot):
    text = message.text or message.caption or "Media xabar"

    async with async_session() as session:
        ticket = await create_support_ticket(session, db_user.tg_id, message.message_id, text)
        admins = await get_admins(session)

    admin_text = (
        f"📞 <b>Yangi support so'rovi #{ticket.id}</b>\n\n"
        f"👤 Foydalanuvchi: <a href='tg://user?id={db_user.tg_id}'>{db_user.full_name}</a>\n"
        f"🆔 ID: <code>{db_user.tg_id}</code>\n"
        f"💬 Xabar:\n<i>{text}</i>"
    )

    for admin in admins:
        try:
            await bot.send_message(
                admin.tg_id,
                admin_text,
                reply_markup=support_reply_kb(db_user.tg_id, ticket.id),
                parse_mode="HTML"
            )
        except Exception:
            pass

    await message.answer(
        "✅ <b>Xabaringiz yuborildi!</b>\n\n"
        "⏳ Admin tez orada javob beradi.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()


# ── Admin support paneli ─────────────────────────────────────

@router.message(F.text == "📞 Support")
async def admin_support_panel(message: Message, db_user: User):
    if not is_admin(db_user):
        return

    async with async_session() as session:
        from database.crud import get_open_tickets
        tickets = await get_open_tickets(session)

    if not tickets:
        await message.answer("✅ Hozircha ochiq supportlar yo'q.")
        return

    await message.answer(f"📞 <b>Ochiq supportlar: {len(tickets)} ta</b>", parse_mode="HTML")

    async with async_session() as session:
        for t in tickets:
            from database.crud import get_user
            user = await get_user(session, t.user_id)
            text = (
                f"📞 <b>Support #{t.id}</b>\n\n"
                f"👤 <a href='tg://user?id={t.user_id}'>{user.full_name if user else t.user_id}</a>\n"
                f"🆔 ID: <code>{t.user_id}</code>\n"
                f"💬 Xabar:\n<i>{t.text[:300]}</i>\n"
                f"🕐 {t.created_at.strftime('%Y-%m-%d %H:%M')}"
            )
            await message.answer(
                text,
                reply_markup=support_reply_kb(t.user_id, t.id),
                parse_mode="HTML"
            )


# ── Admin → foydalanuvchiga javob ───────────────────────────

@router.callback_query(F.data.startswith("reply_ticket:"))
async def admin_reply_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    parts = call.data.split(":")
    user_id = int(parts[1])
    ticket_id = int(parts[2])

    await state.update_data(reply_to_user=user_id, ticket_id=ticket_id)
    await call.message.answer(
        f"💬 Foydalanuvchi ID: <code>{user_id}</code>\n\nJavobingizni yozing:",
        parse_mode="HTML"
    )
    await state.set_state(SupportStates.admin_reply)
    await call.answer()


@router.message(SupportStates.admin_reply)
async def admin_send_reply(message: Message, state: FSMContext, db_user: User, bot: Bot):
    if not is_admin(db_user):
        await state.clear()
        return

    data = await state.get_data()
    user_id = data.get("reply_to_user")
    ticket_id = data.get("ticket_id")

    if not user_id:
        await state.clear()
        return

    try:
        await bot.send_message(
            user_id,
            f"💬 <b>Admin javobi:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer("✅ Javob foydalanuvchiga yuborildi!")

        async with async_session() as session:
            await close_ticket(session, ticket_id)
    except Exception:
        await message.answer(
            "❌ Xabar yuborib bo'lmadi.\n"
            "(Foydalanuvchi botni bloklagan bo'lishi mumkin)"
        )

    await state.clear()


@router.callback_query(F.data.startswith("close_ticket:"))
async def close_ticket_cb(call: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    ticket_id = int(call.data.split(":")[1])

    async with async_session() as session:
        await close_ticket(session, ticket_id)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("✅ Support yopildi!")
