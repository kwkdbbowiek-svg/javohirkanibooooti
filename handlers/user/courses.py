from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.engine import async_session
from database.crud import get_active_courses, get_course, has_purchased
from keyboards.user_kb import courses_kb, course_detail_kb
from utils.helpers import format_money

router = Router(name="user_courses")


@router.callback_query(F.data.startswith("course_view:"))
async def view_course(call: CallbackQuery, db_user):
    course_id = int(call.data.split(":")[1])

    async with async_session() as session:
        course = await get_course(session, course_id)
        if not course:
            await call.answer("Kurs topilmadi!", show_alert=True)
            return
        already_bought = await has_purchased(session, db_user.tg_id, course_id)

    title = course.title
    desc = course.description or "Tavsif mavjud emas"
    price_fmt = format_money(course.price)
    text = f"\U0001F4D6 <b>{title}</b>\n\n\U0001F4DD {desc}\n\n\U0001F4B0 <b>Narxi:</b> {price_fmt}"

    kb = course_detail_kb(course_id, already_bought)

    if course.media_id:
        try:
            if course.media_type == "photo":
                await call.message.answer_photo(course.media_id, caption=text, reply_markup=kb, parse_mode="HTML")
            elif course.media_type == "video":
                await call.message.answer_video(course.media_id, caption=text, reply_markup=kb, parse_mode="HTML")
            else:
                await call.message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await call.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await call.message.answer(text, reply_markup=kb, parse_mode="HTML")

    await call.answer()


@router.callback_query(F.data == "back_to_courses")
async def back_to_courses(call: CallbackQuery):
    async with async_session() as session:
        courses = await get_active_courses(session)

    text = "\U0001F4DA <b>Mavjud kurslar:</b>\n\nQuyidagi kurslardan birini tanlang:"
    await call.message.edit_text(text, reply_markup=courses_kb(courses), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "already_bought")
async def already_bought_cb(call: CallbackQuery):
    await call.answer("\u2705 Siz bu kursni allaqachon sotib olgansiz!", show_alert=True)
