from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from database.engine import async_session
from database.models import User, Course, Purchase
from database.crud import get_user_purchases
from keyboards.user_kb import my_courses_kb, course_link_kb, rating_kb
from utils.helpers import format_money

router = Router(name="my_courses")


@router.message(F.text == "🎓 Mening kurslarim")
async def my_courses(message: Message, db_user: User):
    if db_user.role != "user":
        return

    async with async_session() as session:
        purchases = await get_user_purchases(session, db_user.tg_id)

        if not purchases:
            await message.answer(
                "😔 Siz hali hech qanday kurs sotib olmadingiz.\n\n"
                "📚 Kurslarni koʻrish uchun: <b>📚 Kursni sotib olish</b>",
                parse_mode="HTML"
            )
            return

        course_ids = [p.course_id for p in purchases]
        result = await session.execute(select(Course).where(Course.id.in_(course_ids)))
        courses = {c.id: c for c in result.scalars().all()}

    await message.answer(
        f"🎓 <b>Sizning kurslaringiz ({len(purchases)} ta):</b>\n\nKursni tanlang:",
        reply_markup=my_courses_kb(purchases, courses),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("my_course:"))
async def view_my_course(call: CallbackQuery, db_user: User):
    purchase_id = int(call.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Purchase).where(
                Purchase.id == purchase_id,
                Purchase.user_id == db_user.tg_id,
                Purchase.status == "approved"
            )
        )
        purchase = result.scalar_one_or_none()

        if not purchase:
            await call.answer("Kurs topilmadi!", show_alert=True)
            return

        course = await session.get(Course, purchase.course_id)

    desc = course.description if course and course.description else "Tavsif yoq"
    approved = purchase.approved_at.strftime('%Y-%m-%d') if purchase.approved_at else "—"

    text = (
        f"🎓 <b>{course.title if course else 'Kurs'}</b>\n\n"
        f"📝 {desc}\n\n"
        f"💰 Toʻlangan: <b>{format_money(purchase.amount_paid)}</b>\n"
        f"✅ Tasdiqlangan: <b>{approved}</b>"
    )

    if purchase.rating:
        stars = "⭐" * purchase.rating
        text += f"\n{stars} Sizning bahoyingiz"

    await call.message.answer(
        text,
        reply_markup=course_link_kb(purchase_id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("get_link:"))
async def get_course_link(call: CallbackQuery, db_user: User, bot: Bot):
    purchase_id = int(call.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Purchase).where(
                Purchase.id == purchase_id,
                Purchase.user_id == db_user.tg_id,
                Purchase.status == "approved"
            )
        )
        purchase = result.scalar_one_or_none()

        if not purchase:
            await call.answer("Kurs topilmadi!", show_alert=True)
            return

        course = await session.get(Course, purchase.course_id)

    if not course:
        await call.answer("Kurs maʻlumoti topilmadi!", show_alert=True)
        return

    if course.channel_id:
        try:
            invite = await bot.create_chat_invite_link(
                course.channel_id,
                member_limit=1,
                name=f"User {db_user.tg_id}"
            )
            await call.message.answer(
                f"🔗 <b>Kanalga kirish havolasi:</b>\n\n"
                f"👉 {invite.invite_link}\n\n"
                f"⚠️ <i>Bu havola faqat bir marta ishlatiladi!</i>",
                parse_mode="HTML"
            )
        except Exception:
            link = course.channel_link or "Admin bilan bogʻlaning"
            await call.message.answer(
                f"🔗 <b>Kanalga kirish:</b>\n\n{link}",
                parse_mode="HTML"
            )
    elif course.channel_link:
        await call.message.answer(
            f"🔗 <b>Kanalga kirish:</b>\n\n{course.channel_link}",
            parse_mode="HTML"
        )
    else:
        await call.answer("Kanal havolasi hali sozlanmagan. Admin bilan bogʻlaning.", show_alert=True)

    await call.answer()


@router.callback_query(F.data.startswith("rate:"))
async def rate_course(call: CallbackQuery, db_user: User):
    parts = call.data.split(":")
    purchase_id = int(parts[1])
    rating = int(parts[2])

    async with async_session() as session:
        result = await session.execute(
            select(Purchase).where(
                Purchase.id == purchase_id,
                Purchase.user_id == db_user.tg_id
            )
        )
        purchase = result.scalar_one_or_none()

        if not purchase:
            await call.answer("Topilmadi!", show_alert=True)
            return

        if purchase.rating:
            await call.answer("Siz allaqachon baholadingiz!", show_alert=True)
            return

        purchase.rating = rating
        purchase.rating_reminded = True
        await session.commit()

    stars = "⭐" * rating
    await call.message.edit_text(
        f"✅ <b>Rahmat!</b> Sizning bahoyingiz: {stars}\n\n"
        f"Fikringiz bizga juda muhim! 💙",
        parse_mode="HTML"
    )
    await call.answer(f"Baholandi: {stars}")
