import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.engine import async_session
from database.crud import (
    get_referral_stats, create_withdrawal,
    get_admins, get_referral_bonus,
    get_min_withdrawal, get_user
)
from keyboards.user_kb import withdrawal_kb, main_menu_kb
from keyboards.admin_kb import withdrawal_moderate_kb
from states import WithdrawStates
from utils.helpers import format_money

logger = logging.getLogger(__name__)
router = Router(name="referral")


# ────────────────────────────────────────────────────────────
# Referal tizim sahifasi
# ────────────────────────────────────────────────────────────

@router.message(F.text == "👥 Referal tizim")
async def referral_panel(message: Message, db_user):
    if db_user.role in ("moderator", "superadmin"):
        return

    async with async_session() as session:
        stats        = await get_referral_stats(session, db_user.tg_id)
        bonus_amount = await get_referral_bonus(session)
        min_with     = await get_min_withdrawal(session)
        fresh        = await get_user(session, db_user.tg_id)
        balance      = fresh.balance   if fresh else 0
        withdrawn    = fresh.withdrawn if fresh else 0

    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=REF_{db_user.tg_id}"
    can_withdraw = balance >= min_with

    text = (
        f"👥 <b>Referal tizim</b>\n\n"
        f"🔗 Sizning havolangiz:\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 <b>Statistika:</b>\n"
        f"  👤 Taklif etilganlar: <b>{stats['total']} ta</b>\n"
        f"  🛒 Kurs sotib olganlar: <b>{stats['bought']} ta</b>\n\n"
        f"💰 <b>Balans:</b>\n"
        f"  ✅ Jami bonus: <b>{format_money(stats['bonus_total'])}</b>\n"
        f"  � Yechilgan: <b>{format_money(withdrawn)}</b>\n"
        f"  💵 Qoldiq: <b>{format_money(balance)}</b>\n\n"
        f"🎁 Har bir xarid uchun bonus: <b>{format_money(bonus_amount)}</b>\n"
        f"💳 Minimal yechish summa: <b>{format_money(min_with)}</b>"
    )

    if can_withdraw:
        await message.answer(text, reply_markup=withdrawal_kb(), parse_mode="HTML")
    else:
        remaining = min_with - balance
        text += f"\n\n⏳ Yechish uchun yana <b>{format_money(remaining)}</b> kerak."
        await message.answer(text, parse_mode="HTML")


# ────────────────────────────────────────────────────────────
# Pul yechish — 1: Boshlash
# ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "withdraw_request")
async def withdraw_start(call: CallbackQuery, state: FSMContext, db_user):
    async with async_session() as session:
        min_with = await get_min_withdrawal(session)
        fresh    = await get_user(session, db_user.tg_id)
        balance  = fresh.balance if fresh else 0

    if balance < min_with:
        await call.answer(
            f"❌ Minimal summa: {format_money(min_with)}\n"
            f"Sizning balansingiz: {format_money(balance)}",
            show_alert=True
        )
        return

    await state.update_data(withdraw_balance=balance)
    await call.message.answer(
        f"💳 <b>Pul yechish</b>\n\n"
        f"💵 Mavjud balans: <b>{format_money(balance)}</b>\n\n"
        f"1️⃣ Karta raqamingizni kiriting (16 ta raqam):",
        parse_mode="HTML"
    )
    await state.set_state(WithdrawStates.card_number)
    await call.answer()


# ────────────────────────────────────────────────────────────
# Pul yechish — 2: Karta raqami
# ────────────────────────────────────────────────────────────

@router.message(WithdrawStates.card_number)
async def withdraw_card(message: Message, state: FSMContext):
    raw = message.text.strip().replace(" ", "").replace("-", "")
    if not raw.isdigit() or len(raw) != 16:
        await message.answer(
            "❌ Noto'g'ri format!\n"
            "16 ta raqam kiriting (masalan: 8600123456789012):"
        )
        return
    await state.update_data(card_number=raw)
    await message.answer(
        "2️⃣ Karta egasining <b>to'liq ism-familiyasi</b>ni kiriting\n"
        "<i>(masalan: JOHN DOE yoki Javlon Hasanov)</i>:",
        parse_mode="HTML"
    )
    await state.set_state(WithdrawStates.card_holder)


# ────────────────────────────────────────────────────────────
# Pul yechish — 3: Karta egasi
# ────────────────────────────────────────────────────────────

@router.message(WithdrawStates.card_holder)
async def withdraw_holder(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("❌ To'liq ism-familiya kiriting:")
        return
    await state.update_data(card_holder=name)

    data = await state.get_data()
    balance = data.get("withdraw_balance", 0)

    await message.answer(
        f"3️⃣ Qancha pul yechmoqchisiz?\n\n"
        f"💵 Mavjud balans: <b>{format_money(balance)}</b>\n\n"
        f"Summani kiriting (faqat raqam):",
        parse_mode="HTML"
    )
    await state.set_state(WithdrawStates.amount)


# ────────────────────────────────────────────────────────────
# Pul yechish — 4: Summa va yuborish
# ────────────────────────────────────────────────────────────

@router.message(WithdrawStates.amount)
async def withdraw_amount(message: Message, state: FSMContext, db_user, bot: Bot):
    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Faqat musbat raqam kiriting:")
        return

    # DB dan eng yangi balansni olamiz
    async with async_session() as session:
        min_with = await get_min_withdrawal(session)
        fresh    = await get_user(session, db_user.tg_id)
        balance  = fresh.balance if fresh else 0

    if amount < min_with:
        await message.answer(
            f"❌ Minimal yechish summasi: <b>{format_money(min_with)}</b>\n"
            f"Katta summa kiriting:",
            parse_mode="HTML"
        )
        return

    if amount > balance:
        await message.answer(
            f"❌ Balans yetarli emas!\n"
            f"💵 Joriy balans: <b>{format_money(balance)}</b>\n\n"
            f"Kichikroq summa kiriting:",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    card_number = data["card_number"]
    card_holder = data["card_holder"]

    # So'rovni bazaga yozamiz va balansdan ayiramiz
    async with async_session() as session:
        withdrawal = await create_withdrawal(
            session, db_user.tg_id, card_number, card_holder, amount
        )
        w_id    = withdrawal.id
        admins  = await get_admins(session)
        # session ichida ID larni olamiz
        admin_ids = [a.tg_id for a in admins]

    # Admin ga so'rov yuboramiz
    uname = f"@{db_user.username}" if db_user.username else "yo'q"
    admin_text = (
        f"💸 <b>Yangi pul yechish so'rovi!</b>\n\n"
        f"👤 Foydalanuvchi: <a href='tg://user?id={db_user.tg_id}'>"
        f"{db_user.full_name}</a> ({uname})\n"
        f"🆔 ID: <code>{db_user.tg_id}</code>\n"
        f"💳 Karta: <code>{card_number}</code>\n"
        f"👤 Karta egasi: <b>{card_holder}</b>\n"
        f"💰 Summa: <b>{format_money(amount)}</b>\n\n"
        f"Pul o'tkazib, chekni yuboring."
    )

    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=withdrawal_moderate_kb(w_id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Admin {admin_id} ga xabar yuborishda xato: {e}")

    # Foydalanuvchiga tasdiqlash
    await message.answer(
        f"✅ <b>So'rovingiz yuborildi!</b>\n\n"
        f"💳 Karta: <code>{card_number}</code>\n"
        f"👤 Egasi: <b>{card_holder}</b>\n"
        f"💰 Summa: <b>{format_money(amount)}</b>\n\n"
        f"⏳ Admin pul o'tkazib, chekni yuboradi.\n"
        f"Odatda 24 soat ichida amalga oshiriladi.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()
