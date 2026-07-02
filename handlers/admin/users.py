import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from database.engine import async_session
from database.crud import (
    get_user, block_user, get_users_count,
    get_user_purchases, add_admin_log, get_all_users_ids
)
from database.models import User
from keyboards.admin_kb import user_manage_kb
from states import UserSearchStates
from utils.helpers import is_admin, is_super_admin, format_money

logger = logging.getLogger(__name__)
router = Router(name="admin_users")

PAGE_SIZE = 10


def users_list_kb(users: list, page: int, total: int) -> InlineKeyboardMarkup:
    """Foydalanuvchilar ro'yxati — sahifa bilan"""
    b = InlineKeyboardBuilder()
    for u in users:
        uname = f"@{u.username}" if u.username else f"ID:{u.tg_id}"
        b.row(InlineKeyboardButton(
            text=f"👤 {u.full_name} ({uname})",
            callback_data=f"view_user:{u.tg_id}"
        ))

    # Navigatsiya
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"users_page:{page-1}"))
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    nav.append(InlineKeyboardButton(
        text=f"{page+1}/{total_pages}",
        callback_data="users_page_info"
    ))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"users_page:{page+1}"))
    if nav:
        b.row(*nav)

    b.row(InlineKeyboardButton(text="🔍 Qidirish", callback_data="search_user"))
    return b.as_markup()


@router.message(F.text == "👤 Foydalanuvchilar")
async def users_panel(message: Message, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return

    await state.clear()
    await show_users_page(message, 0)


async def show_users_page(message: Message, page: int):
    async with async_session() as session:
        total = await get_users_count(session)
        offset = page * PAGE_SIZE
        result = await session.execute(
            select(User)
            .order_by(User.registered_at.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
        )
        users = list(result.scalars().all())

    if not users:
        await message.answer("👤 Foydalanuvchilar yo'q.")
        return

    await message.answer(
        f"👤 <b>Foydalanuvchilar</b> (jami: <b>{total:,}</b> ta)\n\n"
        f"Foydalanuvchini tanlang yoki qidiring:",
        reply_markup=users_list_kb(users, page, total),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("users_page:"))
async def users_page_cb(call: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    page = int(call.data.split(":")[1])

    async with async_session() as session:
        total = await get_users_count(session)
        offset = page * PAGE_SIZE
        result = await session.execute(
            select(User)
            .order_by(User.registered_at.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
        )
        users = list(result.scalars().all())

    if not users:
        await call.answer("Sahifa topilmadi!")
        return

    try:
        await call.message.edit_text(
            f"👤 <b>Foydalanuvchilar</b> (jami: <b>{total:,}</b> ta)\n\n"
            f"Foydalanuvchini tanlang yoki qidiring:",
            reply_markup=users_list_kb(users, page, total),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "users_page_info")
async def users_page_info(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data == "search_user")
async def search_user_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return
    await call.message.answer(
        "🔍 Qidirish uchun <b>ID</b> yoki <b>@username</b> yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(UserSearchStates.waiting_for_query)
    await call.answer()


@router.message(UserSearchStates.waiting_for_query)
async def search_user_handler(message: Message, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        await state.clear()
        return

    query = message.text.strip().lstrip("@")

    async with async_session() as session:
        try:
            tg_id = int(query)
            user = await get_user(session, tg_id)
        except ValueError:
            result = await session.execute(
                select(User).where(User.username.ilike(f"%{query}%"))
            )
            user = result.scalar_one_or_none()

    if not user:
        await message.answer(
            "❌ Foydalanuvchi topilmadi.\n\nBoshqa ID yoki @username kiriting:"
        )
        return

    await show_user_detail(message, user)
    await state.clear()


@router.callback_query(F.data.startswith("view_user:"))
async def view_user_cb(call: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    target_id = int(call.data.split(":")[1])

    async with async_session() as session:
        user = await get_user(session, target_id)

    if not user:
        await call.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    await show_user_detail(call.message, user)
    await call.answer()


async def show_user_detail(message: Message, user):
    async with async_session() as session:
        purchases = await get_user_purchases(session, user.tg_id)

    role_emoji = {"superadmin": "👑", "moderator": "🛡", "user": "👤"}.get(user.role, "👤")
    uname    = f"@{user.username}" if user.username else "yo'q"
    blocked  = "Ha 🚫" if user.is_blocked else "Yo'q ✅"
    reg_date = user.registered_at.strftime('%Y-%m-%d') if user.registered_at else "—"

    text = (
        f"👤 <b>Foydalanuvchi</b>\n\n"
        f"🆔 ID: <code>{user.tg_id}</code>\n"
        f"👤 Ism: <a href='tg://user?id={user.tg_id}'>{user.full_name}</a>\n"
        f"📛 Username: {uname}\n"
        f"{role_emoji} Rol: <b>{user.role}</b>\n"
        f"💰 Balans: <b>{format_money(user.balance)}</b>\n"
        f"💳 Yechilgan: <b>{format_money(user.withdrawn)}</b>\n"
        f"📚 Kurslar: <b>{len(purchases)} ta</b>\n"
        f"🚫 Bloklangan: {blocked}\n"
        f"📅 Ro'yxatdan: {reg_date}"
    )

    await message.answer(
        text,
        reply_markup=user_manage_kb(user.tg_id, user.is_blocked),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("toggle_block:"))
async def toggle_block_user(call: CallbackQuery, db_user: User, bot: Bot):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    target_id = int(call.data.split(":")[1])

    if target_id == db_user.tg_id:
        await call.answer("❌ O'zingizni bloklayolmaysiz!", show_alert=True)
        return

    async with async_session() as session:
        target = await get_user(session, target_id)
        if not target:
            await call.answer("Foydalanuvchi topilmadi!", show_alert=True)
            return
        if target.role == "superadmin":
            await call.answer("❌ Super adminni bloklayolmaysiz!", show_alert=True)
            return

        new_blocked = not target.is_blocked
        await block_user(session, target_id, new_blocked)
        await add_admin_log(
            session, db_user.tg_id,
            f"{'Bloklandi' if new_blocked else 'Blokdan chiqarildi'}: {target_id}",
            target_id, "user"
        )

    if new_blocked:
        try:
            await bot.send_message(
                target_id,
                "🚫 Siz botdan foydalanishdan cheklandingiz. Murojaat: @support"
            )
        except Exception:
            pass

    await call.answer("🚫 Bloklandi" if new_blocked else "✅ Blokdan chiqarildi")

    async with async_session() as session:
        updated = await get_user(session, target_id)
    if updated:
        try:
            await call.message.edit_reply_markup(
                reply_markup=user_manage_kb(target_id, updated.is_blocked)
            )
        except Exception:
            pass


@router.callback_query(F.data == "back_to_users")
async def back_to_users(call: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    async with async_session() as session:
        total = await get_users_count(session)
        result = await session.execute(
            select(User).order_by(User.registered_at.desc()).limit(PAGE_SIZE)
        )
        users = list(result.scalars().all())

    try:
        await call.message.edit_text(
            f"👤 <b>Foydalanuvchilar</b> (jami: <b>{total:,}</b> ta)\n\n"
            f"Foydalanuvchini tanlang yoki qidiring:",
            reply_markup=users_list_kb(users, 0, total),
            parse_mode="HTML"
        )
    except Exception:
        await call.message.answer(
            f"👤 <b>Foydalanuvchilar</b> (jami: <b>{total:,}</b> ta)",
            reply_markup=users_list_kb(users, 0, total),
            parse_mode="HTML"
        )
    await call.answer()
