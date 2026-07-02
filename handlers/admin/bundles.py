from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.engine import async_session
from database.crud import (
    get_all_bundles, create_bundle, delete_bundle, add_admin_log
)
from database.models import User
from keyboards.admin_kb import bundles_kb, bundle_detail_kb
from utils.helpers import is_super_admin, format_money

router = Router(name="admin_bundles")


class BundleStates(StatesGroup):
    course_count  = State()
    bundle_price  = State()
    description   = State()
    edit_price    = State()


@router.message(F.text == "🎁 Chegirmalar")
async def show_bundles(message: Message, db_user: User):
    if not is_super_admin(db_user):
        return

    async with async_session() as session:
        bundles = await get_all_bundles(session)

    text = "🎁 <b>Chegirma qoidalari</b>\n\n"
    if bundles:
        for b in bundles:
            text += f"• <b>{b.course_count} ta kurs</b> → {format_money(b.bundle_price)}"
            if b.description:
                text += f" ({b.description})"
            text += "\n"
    else:
        text += "Hozircha chegirma qoidalari yo'q.\n"

    text += "\n<i>Masalan: 2 ta kurs = 150 000 so'm, 3 ta kurs = 250 000 so'm</i>"

    await message.answer(
        text,
        reply_markup=bundles_kb(bundles),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_bundles")
async def back_to_bundles(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    async with async_session() as session:
        bundles = await get_all_bundles(session)

    await call.message.edit_text(
        "🎁 <b>Chegirma qoidalari</b>",
        reply_markup=bundles_kb(bundles),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_bundle:"))
async def bundle_detail(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    bundle_id = int(call.data.split(":")[1])

    async with async_session() as session:
        from sqlalchemy import select
        from database.models import CourseBundle
        r = await session.execute(select(CourseBundle).where(CourseBundle.id == bundle_id))
        b = r.scalar_one_or_none()

    if not b:
        await call.answer("Topilmadi!", show_alert=True)
        return

    text = (
        f"🎁 <b>Chegirma qoidasi</b>\n\n"
        f"📊 Kurslar soni: <b>{b.course_count} ta</b>\n"
        f"💰 Narx: <b>{format_money(b.bundle_price)}</b>\n"
        f"📝 Tavsif: {b.description or '—'}\n"
        f"✅ Status: {'Aktiv' if b.is_active else 'Noaktiv'}"
    )

    await call.message.edit_text(
        text,
        reply_markup=bundle_detail_kb(bundle_id),
        parse_mode="HTML"
    )
    await call.answer()


# ── Qo'shish ─────────────────────────────────────────────────

@router.callback_query(F.data == "add_bundle")
async def add_bundle_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await call.message.answer(
        "🎁 <b>Yangi chegirma qoidasi</b>\n\n"
        "Nechta kurs uchun chegirma? (raqam kiriting)\n"
        "<i>Masalan: 2</i>",
        parse_mode="HTML"
    )
    await state.set_state(BundleStates.course_count)
    await call.answer()


@router.message(BundleStates.course_count)
async def bundle_count_input(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 2:
            raise ValueError
    except ValueError:
        await message.answer("❌ 2 yoki undan katta raqam kiriting:")
        return

    await state.update_data(course_count=count)
    await message.answer(
        f"💰 {count} ta kurs uchun umumiy narx (so'mda):\n"
        f"<i>Masalan: 150000</i>",
        parse_mode="HTML"
    )
    await state.set_state(BundleStates.bundle_price)


@router.message(BundleStates.bundle_price)
async def bundle_price_input(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ To'g'ri narx kiriting:")
        return

    await state.update_data(bundle_price=price)
    await message.answer(
        "📝 Qisqa tavsif kiriting (ixtiyoriy):\n"
        "<i>Masalan: A1 + A2 paket</i>\n\n"
        "Yoki /skip:",
        parse_mode="HTML"
    )
    await state.set_state(BundleStates.description)


@router.message(BundleStates.description)
async def bundle_description_input(message: Message, state: FSMContext, db_user: User):
    desc = None if message.text == "/skip" else message.text.strip()
    data = await state.get_data()

    async with async_session() as session:
        b = await create_bundle(
            session,
            course_count=data["course_count"],
            bundle_price=data["bundle_price"],
            description=desc
        )
        await add_admin_log(
            session, db_user.tg_id,
            f"Bundle yaratildi: {data['course_count']} ta = {data['bundle_price']}",
            b.id, "bundle"
        )

    await message.answer(
        f"✅ <b>Chegirma qo'shildi!</b>\n\n"
        f"📊 {data['course_count']} ta kurs = <b>{format_money(data['bundle_price'])}</b>\n\n"
        f"Endi foydalanuvchi {data['course_count']} ta kurs tanlasa, "
        f"avtomatik {format_money(data['bundle_price'])} to'laydi.",
        parse_mode="HTML"
    )
    await state.clear()


# ── Tahrirlash ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit_bundle:"))
async def edit_bundle_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    bundle_id = int(call.data.split(":")[1])
    await state.update_data(edit_bundle_id=bundle_id)
    await call.message.answer(
        "💰 Yangi narxni kiriting (so'mda):"
    )
    await state.set_state(BundleStates.edit_price)
    await call.answer()


@router.message(BundleStates.edit_price)
async def bundle_edit_price(message: Message, state: FSMContext, db_user: User):
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ To'g'ri narx kiriting:")
        return

    data = await state.get_data()
    bundle_id = data.get("edit_bundle_id")

    async with async_session() as session:
        from sqlalchemy import update as sa_update
        from database.models import CourseBundle
        r = await session.execute(
            select(CourseBundle).where(CourseBundle.id == bundle_id)
        )
        b = r.scalar_one_or_none()
        if b:
            b.bundle_price = price
            await session.commit()
            await add_admin_log(
                session, db_user.tg_id,
                f"Bundle #{bundle_id} narxi o'zgartirildi: {price}",
                bundle_id, "bundle"
            )

    await message.answer(
        f"✅ Narx yangilandi: <b>{format_money(price)}</b>",
        parse_mode="HTML"
    )
    await state.clear()


# ── O'chirish ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete_bundle:"))
async def delete_bundle_cb(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    bundle_id = int(call.data.split(":")[1])

    async with async_session() as session:
        await delete_bundle(session, bundle_id)
        await add_admin_log(
            session, db_user.tg_id,
            f"Bundle #{bundle_id} o'chirildi",
            bundle_id, "bundle"
        )

    await call.message.edit_text("✅ Chegirma qoidasi o'chirildi.")
    await call.answer()
