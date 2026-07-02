from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database.engine import async_session
from database.crud import (
    get_payment_cards, add_payment_card,
    set_default_card, delete_payment_card, add_admin_log
)
from database.models import User, PaymentCard
from keyboards.admin_kb import (
    cards_manage_kb, card_manage_detail_kb, confirm_delete_kb
)
from states import CardStates
from utils.helpers import is_super_admin

router = Router(name="admin_cards")

CARD_TYPES = ["Uzcard", "Humo", "Visa", "MasterCard"]


@router.message(F.text == "💳 Kartalar")
async def show_cards(message: Message, db_user: User):
    if not is_super_admin(db_user):
        return

    async with async_session() as session:
        cards = await get_payment_cards(session)

    await message.answer(
        f"💳 <b>Toʻlov kartalari ({len(cards)} ta):</b>",
        reply_markup=cards_manage_kb(cards),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_cards")
async def back_to_cards(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    async with async_session() as session:
        cards = await get_payment_cards(session)

    await call.message.edit_text(
        f"💳 <b>Toʻlov kartalari ({len(cards)} ta):</b>",
        reply_markup=cards_manage_kb(cards),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_card:"))
async def card_detail(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    card_id = int(call.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(select(PaymentCard).where(PaymentCard.id == card_id))
        card = result.scalar_one_or_none()

    if not card:
        await call.answer("Karta topilmadi!", show_alert=True)
        return

    asosiy = "Ha" if card.is_default else "Yoq"
    text = (
        f"💳 <b>Karta maʻlumotlari</b>\n\n"
        f"🏦 Bank: <b>{card.bank_name}</b>\n"
        f"💳 Turi: <b>{card.card_type}</b>\n"
        f"🔢 Raqam: <code>{card.card_number}</code>\n"
        f"👤 Egasi: <b>{card.holder_name}</b>\n"
        f"⭐ Asosiy: {asosiy}"
    )

    await call.message.edit_text(
        text,
        reply_markup=card_manage_detail_kb(card),
        parse_mode="HTML"
    )
    await call.answer()


# ── Karta qoʻshish ───────────────────────────────────────────

@router.callback_query(F.data == "add_card")
async def add_card_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    await call.message.answer("💳 Karta raqamini kiriting (16 ta raqam):")
    await state.set_state(CardStates.card_number)
    await call.answer()


@router.message(CardStates.card_number)
async def card_number_input(message: Message, state: FSMContext):
    number = message.text.strip().replace(" ", "").replace("-", "")
    if not number.isdigit() or len(number) != 16:
        await message.answer("❌ Notogri format. 16 ta raqam kiriting:")
        return
    await state.update_data(card_number=number)
    await message.answer("👤 Karta egasining toʻliq ismini kiriting:")
    await state.set_state(CardStates.holder_name)


@router.message(CardStates.holder_name)
async def card_holder_input(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("❌ Ism-familiyani toʻliq kiriting:")
        return
    await state.update_data(holder_name=name)
    await message.answer("🏦 Bank nomini kiriting (masalan: Kapitalbank):")
    await state.set_state(CardStates.bank_name)


@router.message(CardStates.bank_name)
async def card_bank_input(message: Message, state: FSMContext):
    await state.update_data(bank_name=message.text.strip())
    await message.answer(
        "💳 Karta turini tanlang:\n\n"
        "1 — Uzcard\n2 — Humo\n3 — Visa\n4 — MasterCard\n\n"
        "Raqam yuboring:"
    )
    await state.set_state(CardStates.card_type)


@router.message(CardStates.card_type)
async def card_type_input(message: Message, state: FSMContext, db_user: User):
    try:
        idx = int(message.text.strip()) - 1
        card_type = CARD_TYPES[idx]
    except (ValueError, IndexError):
        await message.answer("❌ 1-4 orasida raqam kiriting:")
        return

    data = await state.get_data()

    async with async_session() as session:
        cards = await get_payment_cards(session)
        is_default = len(cards) == 0

        card = await add_payment_card(
            session,
            card_number=data["card_number"],
            holder_name=data["holder_name"],
            bank_name=data["bank_name"],
            card_type=card_type,
            is_default=is_default
        )
        await add_admin_log(
            session, db_user.tg_id,
            f"Yangi karta qoʻshildi: ...{data['card_number'][-4:]}",
            card.id, "card"
        )

    default_text = " (Asosiy karta sifatida belgilandi)" if is_default else ""
    await message.answer(
        f"✅ <b>Karta qoʻshildi!</b>\n\n"
        f"💳 {card_type} — <code>{data['card_number']}</code>{default_text}",
        parse_mode="HTML"
    )
    await state.clear()


# ── Default / Delete ─────────────────────────────────────────

@router.callback_query(F.data.startswith("set_default_card:"))
async def set_default_card_cb(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    card_id = int(call.data.split(":")[1])

    async with async_session() as session:
        await set_default_card(session, card_id)
        await add_admin_log(session, db_user.tg_id, f"Karta #{card_id} asosiy qilindi", card_id, "card")

        result = await session.execute(select(PaymentCard).where(PaymentCard.id == card_id))
        card = result.scalar_one_or_none()

    await call.answer("⭐ Asosiy karta sifatida belgilandi!")
    if card:
        await call.message.edit_reply_markup(reply_markup=card_manage_detail_kb(card))


@router.callback_query(F.data.startswith("delete_card:"))
async def delete_card_confirm(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    card_id = int(call.data.split(":")[1])
    await call.message.edit_text(
        "⚠️ <b>Kartani oʻchirishni tasdiqlaysizmi?</b>",
        reply_markup=confirm_delete_kb("delete_card", card_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("confirm_delete_card:"))
async def confirm_delete_card(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yoq!", show_alert=True)
        return

    card_id = int(call.data.split(":")[1])

    async with async_session() as session:
        await delete_payment_card(session, card_id)
        await add_admin_log(session, db_user.tg_id, f"Karta #{card_id} oʻchirildi", card_id, "card")

    await call.message.edit_text("✅ Karta oʻchirildi.")
    await call.answer()


@router.callback_query(F.data == "cancel_delete_card")
async def cancel_delete_card(call: CallbackQuery, db_user: User):
    async with async_session() as session:
        cards = await get_payment_cards(session)
    await call.message.edit_text(
        "💳 <b>Toʻlov kartalari:</b>",
        reply_markup=cards_manage_kb(cards),
        parse_mode="HTML"
    )
    await call.answer()
