from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.engine import async_session
from database.crud import get_admins, set_user_role, add_admin_log, get_user
from database.models import User
from keyboards.admin_kb import admin_roles_kb, manage_admin_kb
from states import AddAdminStates
from utils.helpers import is_super_admin
from config import SUPER_ADMIN_IDS

router = Router(name="admin_admins")


@router.message(F.text == "👮 Adminlar")
async def show_admins(message: Message, db_user: User):
    if not is_super_admin(db_user):
        return

    async with async_session() as session:
        admins = await get_admins(session)

    await message.answer(
        f"👮 <b>Adminlar roʻyxati ({len(admins)} ta):</b>",
        reply_markup=admin_roles_kb(admins),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_admins")
async def back_to_admins(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    async with async_session() as session:
        admins = await get_admins(session)

    await call.message.edit_text(
        f"👮 <b>Adminlar roʻyxati ({len(admins)} ta):</b>",
        reply_markup=admin_roles_kb(admins),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("manage_admin:"))
async def manage_admin(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    target_id = int(call.data.split(":")[1])

    async with async_session() as session:
        target = await get_user(session, target_id)

    if not target:
        await call.answer("Topilmadi!", show_alert=True)
        return

    uname = f"@{target.username}" if target.username else "yoq"
    text = (
        f"👮 <b>Admin: {target.full_name}</b>\n"
        f"🆔 ID: <code>{target.tg_id}</code>\n"
        f"📛 Username: {uname}\n"
        f"🔑 Rol: <b>{target.role}</b>"
    )

    await call.message.edit_text(
        text,
        reply_markup=manage_admin_kb(target.tg_id, target.role),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "add_admin")
async def add_admin_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    await call.message.answer(
        "➕ <b>Yangi admin qoʻshish</b>\n\n"
        "Foydalanuvchining <b>Telegram ID</b>sini kiriting:\n\n"
        "<i>Foydalanuvchi avval botda /start bosgan boʻlishi kerak!</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddAdminStates.waiting_for_id)
    await call.answer()


@router.message(AddAdminStates.waiting_for_id)
async def process_add_admin(message: Message, state: FSMContext, db_user: User, bot: Bot):
    if not is_super_admin(db_user):
        await state.clear()
        return

    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Telegram ID raqam boʻlishi kerak:")
        return

    if target_id == db_user.tg_id:
        await message.answer("❌ Oʻzingizni admin qila olmaysiz!")
        return

    async with async_session() as session:
        target = await get_user(session, target_id)
        if not target:
            await message.answer(
                "❌ Foydalanuvchi topilmadi!\n\n"
                "Foydalanuvchi avval botda /start bosishi kerak."
            )
            return

        if target.role in ("moderator", "superadmin"):
            await message.answer(f"Bu foydalanuvchi allaqachon admin: {target.role}")
            await state.clear()
            return

        await set_user_role(session, target_id, "moderator")
        await add_admin_log(
            session, db_user.tg_id,
            f"Moderator qoʻshildi: {target_id} ({target.full_name})",
            target_id, "admin"
        )

    try:
        await bot.send_message(
            target_id,
            "🛡 <b>Tabriklaymiz!</b>\n\nSiz moderator sifatida tayinlandingiz.\n"
            "Botni qayta ishga tushiring: /start",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await message.answer(
        f"✅ <b>{target.full_name}</b> moderator sifatida qoʻshildi!\n"
        f"🆔 ID: <code>{target_id}</code>",
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("set_role:"))
async def set_role(call: CallbackQuery, db_user: User, bot: Bot):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    parts = call.data.split(":")
    new_role = parts[1]
    target_id = int(parts[2])

    async with async_session() as session:
        await set_user_role(session, target_id, new_role)
        await add_admin_log(
            session, db_user.tg_id,
            f"Rol oʻzgartirildi: {target_id} => {new_role}",
            target_id, "admin"
        )
        target = await get_user(session, target_id)

    try:
        await bot.send_message(
            target_id,
            f"🔑 Sizning rolingiz oʻzgartirildi: <b>{new_role}</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await call.answer(f"✅ Rol {new_role} ga oʻzgartirildi!")
    if target:
        await call.message.edit_reply_markup(
            reply_markup=manage_admin_kb(target_id, new_role)
        )


@router.callback_query(F.data.startswith("remove_admin:"))
async def remove_admin(call: CallbackQuery, db_user: User, bot: Bot):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    target_id = int(call.data.split(":")[1])

    if target_id in SUPER_ADMIN_IDS:
        await call.answer("❌ Super adminni oʻchira olmaysiz!", show_alert=True)
        return

    async with async_session() as session:
        target = await get_user(session, target_id)
        if not target:
            await call.answer("Topilmadi!", show_alert=True)
            return

        await set_user_role(session, target_id, "user")
        await add_admin_log(
            session, db_user.tg_id,
            f"Admin olib tashlandi: {target_id} ({target.full_name})",
            target_id, "admin"
        )

    try:
        await bot.send_message(
            target_id,
            "Sizning admin huquqlaringiz olib tashlandi."
        )
    except Exception:
        pass

    await call.answer("✅ Admin olib tashlandi!")
    await call.message.edit_text(
        f"✅ <b>{target.full_name}</b> adminlikdan olib tashlandi.",
        parse_mode="HTML"
    )


@router.message(F.text == "📋 Admin Loglari")
async def show_admin_logs(message: Message, db_user: User):
    if not is_super_admin(db_user):
        return

    async with async_session() as session:
        from database.crud import get_admin_logs
        logs = await get_admin_logs(session, limit=30)

    if not logs:
        await message.answer("📋 Hozircha loglar yoq.")
        return

    text = "📋 <b>Oxirgi 30 ta admin log:</b>\n\n"
    for log in logs:
        text += (
            f"🕐 {log.timestamp.strftime('%m-%d %H:%M')} | "
            f"<code>{log.admin_id}</code>\n"
            f"▶ {log.action}\n\n"
        )

    if len(text) > 4000:
        text = text[:4000] + "\n... (qolganlar qisqartirildi)"

    await message.answer(text, parse_mode="HTML")
