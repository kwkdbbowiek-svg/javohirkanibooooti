from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database.engine import async_session
from database.crud import (
    get_active_courses, get_course, get_payment_cards,
    create_purchases_group, has_purchased, has_pending_for_courses,
    calculate_price, get_admins, get_shop_header_text, get_bundles,
    get_faq_text
)
from database.models import User, PaymentCard
from keyboards.user_kb import courses_selection_kb, payment_cards_kb, cancel_kb
from keyboards.admin_kb import purchase_moderate_kb
from states import PurchaseStates
from utils.helpers import format_money

router = Router(name="purchase")


@router.message(F.text == "ℹ️ Kurs haqida (FAQ)")
async def show_faq(message: Message, db_user: User):
    if db_user.role in ("moderator", "superadmin"):
        return
    async with async_session() as session:
        text = await get_faq_text(session)
    await message.answer(text, parse_mode="HTML")


async def _build_shop_text(header: str, bundles: list) -> str:
    """Header matn + chegirmalar ro'yxati"""
    text = header
    if bundles:
        text += "\n\n💡 <b>Chegirmalar:</b>\n"
        for b in bundles:
            desc = f" ({b.description})" if b.description else ""
            text += f"• {b.course_count} ta kurs = {format_money(b.bundle_price)}{desc}\n"
    return text


# ── Kurs tanlash ─────────────────────────────────────────────

@router.message(F.text == "📚 Kursni sotib olish")
async def show_courses(message: Message, db_user: User, state: FSMContext):
    if db_user.role in ("moderator", "superadmin"):
        return

    async with async_session() as session:
        courses  = await get_active_courses(session)
        header   = await get_shop_header_text(session)
        bundles  = await get_bundles(session)

    if not courses:
        await message.answer("😔 Hozircha aktiv kurslar mavjud emas. Kechroq qarang!")
        return

    # Allaqachon sotib olinganlarni chiqarib tashlash
    already_ids = []
    async with async_session() as session:
        for c in courses:
            if await has_purchased(session, db_user.tg_id, c.id):
                already_ids.append(c.id)

    available = [c for c in courses if c.id not in already_ids]
    if not available:
        await message.answer("✅ Siz barcha mavjud kurslarni sotib olgansiz!")
        return

    # State tozalash — yangi tanlash
    await state.update_data(selected_courses=[])

    shop_text = await _build_shop_text(header, bundles)

    await message.answer(
        shop_text,
        reply_markup=courses_selection_kb(available, [], 0, 0),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pick_course:"))
async def pick_course_selection(call: CallbackQuery, state: FSMContext, db_user: User):
    course_id = int(call.data.split(":")[1])

    data = await state.get_data()
    selected: list[int] = list(data.get("selected_courses", []))

    if course_id in selected:
        selected.remove(course_id)
    else:
        selected.append(course_id)

    await state.update_data(selected_courses=selected)

    async with async_session() as session:
        courses = await get_active_courses(session)
        already_ids = []
        for c in courses:
            if await has_purchased(session, db_user.tg_id, c.id):
                already_ids.append(c.id)
        available = [c for c in courses if c.id not in already_ids]

        if selected:
            original, final, _ = await calculate_price(session, selected)
        else:
            original, final = 0, 0

    try:
        await call.message.edit_reply_markup(
            reply_markup=courses_selection_kb(available, selected, original, final)
        )
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "proceed_purchase")
async def proceed_to_payment(call: CallbackQuery, state: FSMContext, db_user: User):
    data = await state.get_data()
    selected: list[int] = list(data.get("selected_courses", []))

    if not selected:
        await call.answer("❌ Hech qanday kurs tanlanmadi!", show_alert=True)
        return

    async with async_session() as session:
        # Pending tekshiruvi
        if await has_pending_for_courses(session, db_user.tg_id, selected):
            await call.answer(
                "⏳ Tanlangan kurslardan biri allaqachon tekshirilmoqda!",
                show_alert=True
            )
            return

        # Allaqachon sotib olinganlarni chiqarib tashlash
        new_selected = []
        for cid in selected:
            if not await has_purchased(session, db_user.tg_id, cid):
                new_selected.append(cid)

        if not new_selected:
            await call.answer("✅ Tanlangan kurslarni allaqachon olgansiz!", show_alert=True)
            return

        original, final, _ = await calculate_price(session, new_selected)
        cards = await get_payment_cards(session)

        course_titles = []
        for cid in new_selected:
            c = await get_course(session, cid)
            if c:
                course_titles.append(c.title)

    await state.update_data(
        selected_courses=new_selected,
        original_price=original,
        final_price=final,
        course_titles=course_titles
    )

    if not cards:
        await call.message.answer(
            "❌ Hozircha to'lov kartalari yo'q. Admin bilan bog'laning.",
            parse_mode="HTML"
        )
        return

    courses_text = "\n".join(f"  • {t}" for t in course_titles)
    if original != final:
        price_text = (
            f"💰 Asl narx: <s>{format_money(original)}</s>\n"
            f"🎁 Chegirma bilan: <b>{format_money(final)}</b>"
        )
    else:
        price_text = f"💰 Jami: <b>{format_money(final)}</b>"

    await call.message.answer(
        f"🛒 <b>Tanlangan kurslar:</b>\n{courses_text}\n\n"
        f"{price_text}\n\n"
        f"💳 <b>To'lov kartasini tanlang:</b>",
        reply_markup=payment_cards_kb(cards),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("select_card:"))
async def select_card(call: CallbackQuery, state: FSMContext, db_user: User):
    card_id = int(call.data.split(":")[1])
    data = await state.get_data()

    if not data.get("selected_courses"):
        await call.answer("Sessiya tugagan. Qayta boshlang.", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(PaymentCard).where(
                PaymentCard.id == card_id,
                PaymentCard.is_active == True
            )
        )
        card = result.scalar_one_or_none()

    if not card:
        await call.answer("Karta topilmadi!", show_alert=True)
        return

    final_price    = data.get("final_price", 0)
    original_price = data.get("original_price", 0)
    course_titles  = data.get("course_titles", [])

    courses_text = "\n".join(f"  • {t}" for t in course_titles)
    if original_price != final_price:
        price_text = (
            f"💰 Asl narx: <s>{format_money(original_price)}</s>\n"
            f"🎁 Chegirma bilan: <b>{format_money(final_price)}</b>"
        )
    else:
        price_text = f"💰 Jami: <b>{format_money(final_price)}</b>"

    await state.update_data(selected_card_id=card_id)

    await call.message.answer(
        f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
        f"🏦 Bank: <b>{card.bank_name}</b> ({card.card_type})\n"
        f"💳 Karta raqami: <code>{card.card_number}</code>\n"
        f"👤 Egasi: <b>{card.holder_name}</b>\n\n"
        f"📚 <b>Kurslar:</b>\n{courses_text}\n\n"
        f"{price_text}\n\n"
        f"📋 <b>Ko'rsatma:</b>\n"
        f"1. Yuqoridagi karta raqamiga <b>{format_money(final_price)}</b> o'tkazing\n"
        f"2. To'lov chekini (skrinshot) <b>rasm sifatida</b> yuboring\n\n"
        f"⚠️ <i>Faqat rasm (photo) ko'rinishidagi chek qabul qilinadi!</i>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(PurchaseStates.waiting_for_receipt)
    await call.answer()


@router.message(PurchaseStates.waiting_for_receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext, db_user: User, bot: Bot):
    data = await state.get_data()
    selected       = data.get("selected_courses", [])
    final_price    = data.get("final_price", 0)
    original_price = data.get("original_price", 0)
    course_titles  = data.get("course_titles", [])

    if not selected:
        await message.answer("❌ Sessiya tugagan. Qayta boshlang.")
        await state.clear()
        return

    photo_id = message.photo[-1].file_id

    async with async_session() as session:
        # Idempotency
        if await has_pending_for_courses(session, db_user.tg_id, selected):
            await message.answer("⏳ So'rovingiz allaqachon tekshirilmoqda!")
            await state.clear()
            return

        group_id = await create_purchases_group(
            session, db_user.tg_id, selected,
            photo_id, final_price, original_price
        )
        admins = await get_admins(session)
        admin_ids = [a.tg_id for a in admins]

    # Admin uchun xabar
    courses_text = "\n".join(f"  • {t}" for t in course_titles)
    if original_price != final_price:
        price_text = (
            f"💰 Asl: {format_money(original_price)}\n"
            f"🎁 Chegirma bilan: <b>{format_money(final_price)}</b>"
        )
    else:
        price_text = f"💰 Summa: <b>{format_money(final_price)}</b>"

    admin_text = (
        f"🆕 <b>Yangi to'lov so'rovi!</b>\n\n"
        f"👤 <a href='tg://user?id={db_user.tg_id}'>{db_user.full_name}</a>\n"
        f"🆔 <code>{db_user.tg_id}</code>\n"
        f"📚 Kurslar ({len(selected)} ta):\n{courses_text}\n\n"
        f"{price_text}\n"
        f"🕐 {message.date.strftime('%Y-%m-%d %H:%M')}"
    )

    for admin_id in admin_ids:
        try:
            await bot.send_photo(
                admin_id,
                photo=photo_id,
                caption=admin_text,
                reply_markup=purchase_moderate_kb(group_id),
                parse_mode="HTML"
            )
        except Exception:
            pass

    await message.answer(
        "✅ <b>Chekingiz qabul qilindi!</b>\n\n"
        "⏳ Admin tekshirib, har bir kurs uchun kanal havolasini yuboradi.\n"
        "Odatda 10-30 daqiqa ichida tasdiqlanadi.",
        parse_mode="HTML"
    )
    await state.clear()


@router.message(PurchaseStates.waiting_for_receipt)
async def receipt_wrong_format(message: Message):
    await message.answer(
        "❌ Iltimos, to'lov chekini <b>rasm (photo)</b> ko'rinishida yuboring!\n\n"
        "📸 Telefonda skrinshot olib, uni shu chatga yuboring.",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel_purchase")
async def cancel_purchase(call: CallbackQuery, state: FSMContext):
    await state.clear()
    from keyboards.user_kb import main_menu_kb
    await call.message.answer("❌ Bekor qilindi.", reply_markup=main_menu_kb())
    await call.answer()
