from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.engine import async_session
from database.crud import (
    get_all_courses, get_course, create_course,
    update_course, soft_delete_course, add_admin_log
)
from database.models import User
from keyboards.admin_kb import (
    courses_manage_kb, course_manage_detail_kb,
    course_edit_fields_kb, confirm_delete_kb
)
from states import CourseStates
from utils.helpers import is_super_admin, format_money

router = Router(name="admin_courses")


@router.message(F.text == "📚 Kurslar")
async def show_courses_admin(message: Message, db_user: User):
    if not is_super_admin(db_user):
        return

    async with async_session() as session:
        courses = await get_all_courses(session)

    if not courses:
        await message.answer(
            "📚 Hozircha kurslar yo'q.",
            reply_markup=courses_manage_kb([])
        )
        return

    await message.answer(
        f"📚 <b>Kurslar ro'yxati ({len(courses)} ta):</b>",
        reply_markup=courses_manage_kb(courses),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_courses_admin")
async def back_to_courses_admin(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    async with async_session() as session:
        courses = await get_all_courses(session)

    await call.message.edit_text(
        f"📚 <b>Kurslar ro'yxati ({len(courses)} ta):</b>",
        reply_markup=courses_manage_kb(courses),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_course:"))
async def course_detail_admin(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    course_id = int(call.data.split(":")[1])

    async with async_session() as session:
        course = await get_course(session, course_id)

    if not course:
        await call.answer("Kurs topilmadi!", show_alert=True)
        return

    status = "✅ Aktiv" if course.is_active else "🔴 Noaktiv"
    text = (
        f"📖 <b>{course.title}</b>\n\n"
        f"📝 {course.description or '—'}\n\n"
        f"💰 Narx: <b>{format_money(course.price)}</b>\n"
        f"📊 Status: {status}\n"
        f"🔗 Kanal: {course.channel_link or '—'}"
    )

    await call.message.edit_text(
        text,
        reply_markup=course_manage_detail_kb(course),
        parse_mode="HTML"
    )
    await call.answer()


# ── ADD COURSE FLOW ──────────────────────────────────────────

@router.callback_query(F.data == "add_course")
async def add_course_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await call.message.answer("📝 Kurs nomini kiriting:")
    await state.set_state(CourseStates.title)
    await call.answer()


@router.message(CourseStates.title)
async def course_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("📄 Kurs tavsifini kiriting (yoki /skip):")
    await state.set_state(CourseStates.description)


@router.message(CourseStates.description)
async def course_description(message: Message, state: FSMContext):
    desc = None if message.text == "/skip" else message.text.strip()
    await state.update_data(description=desc)
    await message.answer("💰 Kurs narxini kiriting (faqat raqam, so'mda):")
    await state.set_state(CourseStates.price)


@router.message(CourseStates.price)
async def course_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Narxni to'g'ri kiriting (masalan: 150000):")
        return

    await state.update_data(price=price)
    await message.answer(
        "🖼 Kurs rasmi yoki videosini yuboring (yoki /skip):\n\n"
        "<i>Rasm yoki video fayl yuboring</i>",
        parse_mode="HTML"
    )
    await state.set_state(CourseStates.media)


@router.message(CourseStates.media)
async def course_media(message: Message, state: FSMContext):
    media_id = None
    media_type = None

    if message.text == "/skip":
        pass
    elif message.photo:
        media_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_id = message.video.file_id
        media_type = "video"
    else:
        await message.answer("❌ Rasm yoki video yuboring, yoki /skip:")
        return

    await state.update_data(media_id=media_id, media_type=media_type)
    await message.answer(
        "🔗 Yopiq kanal/guruh Invite Link kiriting:\n"
        "(masalan: https://t.me/+AbCdEfGhIjKl)\n\n"
        "Yoki /skip:"
    )
    await state.set_state(CourseStates.channel_link)


@router.message(CourseStates.channel_link)
async def course_channel_link(message: Message, state: FSMContext):
    link = None if message.text == "/skip" else message.text.strip()
    await state.update_data(channel_link=link)
    await message.answer(
        "🆔 Kanal ID kiriting (masalan: -1001234567890)\n"
        "Invite link yuborish uchun kanal ID kerak.\n\n"
        "Yoki /skip:"
    )
    await state.set_state(CourseStates.channel_id)


@router.message(CourseStates.channel_id)
async def course_channel_id(message: Message, state: FSMContext, db_user: User):
    channel_id = None
    if message.text != "/skip":
        try:
            channel_id = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Kanal ID raqam bo'lishi kerak (masalan: -1001234567890):")
            return

    data = await state.get_data()

    async with async_session() as session:
        course = await create_course(
            session,
            title=data["title"],
            description=data.get("description"),
            price=data["price"],
            media_id=data.get("media_id"),
            media_type=data.get("media_type"),
            channel_link=data.get("channel_link"),
            channel_id=channel_id
        )
        await add_admin_log(session, db_user.tg_id, f"Yangi kurs yaratdi: {data['title']}", course.id, "course")

    await message.answer(
        f"✅ <b>Kurs muvaffaqiyatli yaratildi!</b>\n\n"
        f"📖 Nomi: <b>{data['title']}</b>\n"
        f"💰 Narxi: <b>{format_money(data['price'])}</b>",
        parse_mode="HTML"
    )
    await state.clear()


# ── EDIT COURSE ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit_course:"))
async def edit_course_menu(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    course_id = int(call.data.split(":")[1])
    async with async_session() as session:
        course = await get_course(session, course_id)

    if not course:
        await call.answer("Kurs topilmadi!", show_alert=True)
        return

    await call.message.edit_text(
        f"✏️ <b>{course.title}</b> kursini tahrirlang:\n\nQaysi maydonni o'zgartirmoqchisiz?",
        reply_markup=course_edit_fields_kb(course_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def edit_field_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    parts = call.data.split(":")
    course_id = int(parts[1])
    field = parts[2]

    field_names = {
        "title": "Nomi",
        "description": "Tavsifi",
        "price": "Narxi (so'mda raqam kiriting)",
        "channel_link": "Kanal havolasi",
        "media": "Rasm yoki video yuboring"
    }

    await state.update_data(edit_course_id=course_id, edit_field=field)
    await call.message.answer(f"✏️ Yangi <b>{field_names.get(field, field)}</b>ni kiriting:", parse_mode="HTML")
    await state.set_state(CourseStates.edit_field)
    await call.answer()


@router.message(CourseStates.edit_field)
async def process_edit_field(message: Message, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await state.clear()
        return

    data = await state.get_data()
    course_id = data["edit_course_id"]
    field = data["edit_field"]

    update_data = {}

    if field == "title":
        update_data["title"] = message.text.strip()
    elif field == "description":
        update_data["description"] = message.text.strip()
    elif field == "price":
        try:
            price = int(message.text.strip().replace(" ", "").replace(",", ""))
            update_data["price"] = price
        except ValueError:
            await message.answer("❌ Narxni to'g'ri kiriting:")
            return
    elif field == "channel_link":
        update_data["channel_link"] = message.text.strip()
    elif field == "media":
        if message.photo:
            update_data["media_id"] = message.photo[-1].file_id
            update_data["media_type"] = "photo"
        elif message.video:
            update_data["media_id"] = message.video.file_id
            update_data["media_type"] = "video"
        else:
            await message.answer("❌ Rasm yoki video yuboring:")
            return

    async with async_session() as session:
        await update_course(session, course_id, **update_data)
        await add_admin_log(
            session, db_user.tg_id,
            f"Kurs #{course_id} tahrirlandi: {field}",
            course_id, "course"
        )

    await message.answer(f"✅ <b>{field}</b> muvaffaqiyatli yangilandi!", parse_mode="HTML")
    await state.clear()


# ── TOGGLE / DELETE ──────────────────────────────────────────

@router.callback_query(F.data.startswith("toggle_course:"))
async def toggle_course(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    course_id = int(call.data.split(":")[1])

    async with async_session() as session:
        course = await get_course(session, course_id)
        if not course:
            await call.answer("Topilmadi!", show_alert=True)
            return

        new_status = not course.is_active
        await update_course(session, course_id, is_active=new_status)
        await add_admin_log(
            session, db_user.tg_id,
            f"Kurs #{course_id} {'aktiv' if new_status else 'noaktiv'} qilindi",
            course_id, "course"
        )
        course.is_active = new_status

    status_text = "✅ Aktiv" if new_status else "🔴 Noaktiv"
    await call.answer(f"Kurs {status_text} qilindi!")
    await call.message.edit_reply_markup(reply_markup=course_manage_detail_kb(course))


@router.callback_query(F.data.startswith("delete_course:"))
async def delete_course_confirm(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    course_id = int(call.data.split(":")[1])
    await call.message.edit_text(
        "⚠️ <b>Kursni o'chirishni tasdiqlaysizmi?</b>\n\n"
        "Eski xaridorlar kursga kirishda qolaveradi (Soft Delete).",
        reply_markup=confirm_delete_kb("delete_course", course_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("confirm_delete_course:"))
async def confirm_delete_course(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    course_id = int(call.data.split(":")[1])

    async with async_session() as session:
        await soft_delete_course(session, course_id)
        await add_admin_log(
            session, db_user.tg_id,
            f"Kurs #{course_id} o'chirildi (soft delete)",
            course_id, "course"
        )

    await call.message.edit_text("✅ Kurs o'chirildi (eski xaridorlar ta'sirlanmadi).")
    await call.answer()


@router.callback_query(F.data == "cancel_delete_course")
async def cancel_delete_course(call: CallbackQuery, db_user: User):
    async with async_session() as session:
        courses = await get_all_courses(session)
    await call.message.edit_text(
        f"📚 <b>Kurslar ro'yxati:</b>",
        reply_markup=courses_manage_kb(courses),
        parse_mode="HTML"
    )
    await call.answer()
