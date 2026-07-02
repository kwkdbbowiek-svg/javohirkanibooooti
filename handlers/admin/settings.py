from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.engine import async_session
from database.crud import get_all_settings, set_setting, add_admin_log
from database.models import User
from keyboards.admin_kb import settings_kb
from utils.helpers import is_super_admin, format_money

router = Router(name="admin_settings")


class SettingsStates(StatesGroup):
    edit_referral_bonus  = State()
    edit_min_withdrawal  = State()
    edit_faq             = State()
    edit_shop_header     = State()


SETTING_LABELS = {
    "referral_bonus":   "💰 Referal bonus (so'm)",
    "min_withdrawal":   "💳 Minimal yechish (so'm)",
    "faq_text":         "ℹ️ FAQ matni",
    "shop_header_text": "📚 Kurs sahifasi matni",
}


# ── Sozlamalar menyusi ───────────────────────────────────────

@router.message(F.text == "⚙️ Sozlamalar")
async def show_settings(message: Message, db_user: User):
    if not is_super_admin(db_user):
        return

    async with async_session() as session:
        s = await get_all_settings(session)

    ref_bonus  = int(s.get("referral_bonus", 20000))
    min_with   = int(s.get("min_withdrawal",  50000))
    faq_prev   = s.get("faq_text", "")[:60] + "..." if len(s.get("faq_text","")) > 60 else s.get("faq_text","—")
    shop_prev  = s.get("shop_header_text", "")[:60] + "..." if len(s.get("shop_header_text","")) > 60 else s.get("shop_header_text","—")

    text = (
        "⚙️ <b>Bot sozlamalari</b>\n\n"
        f"💰 Referal bonus: <b>{format_money(ref_bonus)}</b>\n"
        f"💳 Minimal yechish: <b>{format_money(min_with)}</b>\n"
        f"ℹ️ FAQ: <i>{faq_prev}</i>\n"
        f"📚 Kurs sahifasi: <i>{shop_prev}</i>\n\n"
        "O'zgartirish uchun tugma bosing:"
    )
    await message.answer(text, reply_markup=settings_kb(), parse_mode="HTML")


# ── Referal bonus ────────────────────────────────────────────

@router.callback_query(F.data == "edit_setting:referral_bonus")
async def edit_referral_bonus(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    async with async_session() as session:
        s = await get_all_settings(session)

    current = int(s.get("referral_bonus", 20000))
    await call.message.answer(
        f"💰 <b>Referal bonus</b>\n\n"
        f"Hozirgi: <b>{format_money(current)}</b>\n\n"
        f"Yangi summani kiriting (so'mda):\n<i>Masalan: 25000</i>",
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.edit_referral_bonus)
    await call.answer()


@router.message(SettingsStates.edit_referral_bonus)
async def save_referral_bonus(message: Message, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await state.clear()
        return
    try:
        value = int(message.text.strip().replace(" ", "").replace(",", ""))
        if value < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri qiymat. Musbat raqam kiriting:")
        return

    async with async_session() as session:
        await set_setting(session, "referral_bonus", str(value))
        await add_admin_log(session, db_user.tg_id,
                            f"Referal bonus: {value}", None, "settings")

    await message.answer(
        f"✅ Referal bonus yangilandi: <b>{format_money(value)}</b>",
        parse_mode="HTML"
    )
    await state.clear()


# ── Minimal yechish ──────────────────────────────────────────

@router.callback_query(F.data == "edit_setting:min_withdrawal")
async def edit_min_withdrawal(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    async with async_session() as session:
        s = await get_all_settings(session)

    current = int(s.get("min_withdrawal", 50000))
    await call.message.answer(
        f"💳 <b>Minimal yechish summasi</b>\n\n"
        f"Hozirgi: <b>{format_money(current)}</b>\n\n"
        f"Yangi summani kiriting (so'mda):\n<i>Masalan: 50000</i>",
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.edit_min_withdrawal)
    await call.answer()


@router.message(SettingsStates.edit_min_withdrawal)
async def save_min_withdrawal(message: Message, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await state.clear()
        return
    try:
        value = int(message.text.strip().replace(" ", "").replace(",", ""))
        if value < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri qiymat. Musbat raqam kiriting:")
        return

    async with async_session() as session:
        await set_setting(session, "min_withdrawal", str(value))
        await add_admin_log(session, db_user.tg_id,
                            f"Min yechish: {value}", None, "settings")

    await message.answer(
        f"✅ Minimal yechish yangilandi: <b>{format_money(value)}</b>",
        parse_mode="HTML"
    )
    await state.clear()


# ── FAQ ──────────────────────────────────────────────────────

@router.callback_query(F.data == "edit_setting:faq_text")
async def edit_faq(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    async with async_session() as session:
        s = await get_all_settings(session)
    current = s.get("faq_text", "")[:300]

    await call.message.answer(
        "ℹ️ <b>FAQ matnini tahrirlash</b>\n\n"
        f"Hozirgi:\n<i>{current}</i>\n\n"
        "Yangi FAQ matnini yuboring.\n"
        "HTML teglar: <b>bold</b>, <i>italic</i>, <code>kod</code>",
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.edit_faq)
    await call.answer()


@router.message(SettingsStates.edit_faq)
async def save_faq(message: Message, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await state.clear()
        return

    faq_text = message.text or message.caption or ""
    if not faq_text.strip():
        await message.answer("❌ Matn bo'sh. Qayta yuboring:")
        return

    async with async_session() as session:
        await set_setting(session, "faq_text", faq_text)
        await add_admin_log(session, db_user.tg_id, "FAQ yangilandi", None, "settings")

    await message.answer("✅ <b>FAQ yangilandi!</b>\n\nPreview:", parse_mode="HTML")
    await message.answer(faq_text, parse_mode="HTML")
    await state.clear()


# ── Kurs sahifasi matni ──────────────────────────────────────

@router.callback_query(F.data == "edit_setting:shop_header_text")
async def edit_shop_header(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    async with async_session() as session:
        s = await get_all_settings(session)
    current = s.get("shop_header_text", "")[:300]

    await call.message.answer(
        "📚 <b>Kurs sahifasi matnini tahrirlash</b>\n\n"
        f"Hozirgi:\n<i>{current}</i>\n\n"
        "Yangi matnni yuboring.\n"
        "HTML teglar ishlaydi: <b>bold</b>, <i>italic</i>\n\n"
        "<b>Eslatma:</b> Bu matn kurs tanlash sahifasida "
        "kurslar ro'yxatidan YUQORIDA chiqadi.\n"
        "Chegirmalar avtomatik qo'shiladi.",
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.edit_shop_header)
    await call.answer()


@router.message(SettingsStates.edit_shop_header)
async def save_shop_header(message: Message, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await state.clear()
        return

    text = message.text or message.caption or ""
    if not text.strip():
        await message.answer("❌ Matn bo'sh. Qayta yuboring:")
        return

    async with async_session() as session:
        await set_setting(session, "shop_header_text", text)
        await add_admin_log(session, db_user.tg_id,
                            "Kurs sahifasi matni yangilandi", None, "settings")

    await message.answer("✅ <b>Kurs sahifasi matni yangilandi!</b>", parse_mode="HTML")
    await state.clear()
