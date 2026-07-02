import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import update, select

from database.engine import async_session
from database.models import Purchase, Course
from database.crud import get_purchases_for_rating_reminder, get_abandoned_cart_users
from keyboards.user_kb import rating_kb
from utils.helpers import format_money

logger = logging.getLogger(__name__)


async def send_rating_reminders(bot: Bot):
    """24 soatdan keyin kursni baholash eslatmasi yuboradi"""
    try:
        async with async_session() as session:
            purchases = await get_purchases_for_rating_reminder(session)

        for purchase in purchases:
            try:
                async with async_session() as session:
                    result = await session.execute(
                        select(Course).where(Course.id == purchase.course_id)
                    )
                    course = result.scalar_one_or_none()

                    # Mark as reminded
                    await session.execute(
                        update(Purchase)
                        .where(Purchase.id == purchase.id)
                        .values(rating_reminded=True)
                    )
                    await session.commit()

                course_name = course.title if course else "Kurs"

                await bot.send_message(
                    purchase.user_id,
                    f"⭐ <b>Kursni baholang!</b>\n\n"
                    f"📚 <b>{course_name}</b> kursini qanday baholaysiz?\n\n"
                    f"Sizning fikringiz bizga juda muhim! 💙",
                    reply_markup=rating_kb(purchase.id),
                    parse_mode="HTML"
                )
                await asyncio.sleep(0.05)

            except Exception as e:
                logger.warning(f"Rating reminder failed for user {purchase.user_id}: {e}")

    except Exception as e:
        logger.error(f"send_rating_reminders error: {e}")


async def send_abandoned_cart_reminders(bot: Bot):
    """2 soat va 24 soatdan keyin to'lovni yakunlamaganlarni eslatadi"""
    try:
        async with async_session() as session:
            purchases = await get_abandoned_cart_users(session)

        now = datetime.utcnow()

        for purchase in purchases:
            try:
                elapsed_hours = (now - purchase.created_at).total_seconds() / 3600

                async with async_session() as session:
                    result = await session.execute(
                        select(Course).where(Course.id == purchase.course_id)
                    )
                    course = result.scalar_one_or_none()

                if not course:
                    continue

                # 2 soatlik eslatma (2-3 soat oralig'ida)
                if 2.0 <= elapsed_hours < 3.0:
                    await bot.send_message(
                        purchase.user_id,
                        f"⏰ <b>Eslatma!</b>\n\n"
                        f"📚 <b>{course.title}</b> kursini sotib olishni unutmadingizmi?\n\n"
                        f"To'lovni yakunlang va kursga kirish imkoniyatiga ega bo'ling! 🎓\n\n"
                        f"💰 Narxi: <b>{format_money(course.price)}</b>",
                        parse_mode="HTML"
                    )

                # 24 soatlik eslatma (24-25 soat oralig'ida)
                elif 24.0 <= elapsed_hours < 25.0:
                    await bot.send_message(
                        purchase.user_id,
                        f"🔔 <b>Sizni kutmoqdamiz!</b>\n\n"
                        f"📚 <b>{course.title}</b> — {format_money(course.price)}\n\n"
                        f"To'lovni yakunlang va bugun o'qishni boshlang! 🚀",
                        parse_mode="HTML"
                    )

                await asyncio.sleep(0.05)

            except Exception as e:
                logger.warning(f"Abandoned cart reminder failed for user {purchase.user_id}: {e}")

    except Exception as e:
        logger.error(f"send_abandoned_cart_reminders error: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

    # Har soatda rating reminder tekshiruvi
    scheduler.add_job(
        send_rating_reminders,
        trigger="interval",
        hours=1,
        kwargs={"bot": bot},
        id="rating_reminders",
        replace_existing=True
    )

    # Har 30 daqiqada abandoned cart tekshiruvi
    scheduler.add_job(
        send_abandoned_cart_reminders,
        trigger="interval",
        minutes=30,
        kwargs={"bot": bot},
        id="abandoned_cart",
        replace_existing=True
    )

    return scheduler
