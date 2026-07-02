from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from database.engine import async_session
from database.crud import (
    get_users_count, get_today_users_count,
    get_buyers_count, get_today_buyers_count,
    get_total_sales_count, get_total_revenue,
    get_today_revenue, get_top_course
)
from database.models import User
from keyboards.admin_kb import stats_filter_kb
from utils.helpers import is_admin, format_money
from utils.excel_export import export_to_excel

router = Router(name="admin_stats")


def admin_only(func):
    async def wrapper(event, db_user: User, **kwargs):
        if not is_admin(db_user):
            if hasattr(event, 'answer'):
                await event.answer("❌ Ruxsat yo'q!")
            return
        return await func(event, db_user=db_user, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@router.message(F.text == "📊 Statistika")
async def show_stats(message: Message, db_user: User):
    if not is_admin(db_user):
        return

    async with async_session() as session:
        total_users = await get_users_count(session)
        today_users = await get_today_users_count(session)
        total_buyers = await get_buyers_count(session)
        today_buyers = await get_today_buyers_count(session)
        total_sales = await get_total_sales_count(session)
        total_revenue = await get_total_revenue(session)
        today_revenue = await get_today_revenue(session)
        top_course = await get_top_course(session)

    top_text = f"🏆 <b>{top_course[0]}</b> — {top_course[1]} ta" if top_course else "Ma'lumot yo'q"

    text = (
        f"📊 <b>BOT STATISTIKASI</b>\n"
        f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} (UTC)\n\n"
        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"├ Jami: <b>{total_users:,}</b>\n"
        f"└ Bugun: <b>+{today_users}</b>\n\n"
        f"🛒 <b>Xaridlar:</b>\n"
        f"├ Jami xaridorlar: <b>{total_buyers:,}</b>\n"
        f"├ Bugun xaridorlar: <b>+{today_buyers}</b>\n"
        f"└ Jami sotilgan kurslar: <b>{total_sales:,}</b>\n\n"
        f"💰 <b>Daromad:</b>\n"
        f"├ Jami: <b>{format_money(total_revenue)}</b>\n"
        f"└ Bugun: <b>{format_money(today_revenue)}</b>\n\n"
        f"🏆 <b>Top kurs:</b>\n{top_text}"
    )

    await message.answer(text, reply_markup=stats_filter_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("stats_filter:"))
async def stats_filter(call: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    days = int(call.data.split(":")[1])

    async with async_session() as session:
        if days > 0:
            from sqlalchemy import select, func
            from database.models import Purchase, User as UserModel
            from database.crud import get_top_course
            since = datetime.utcnow() - timedelta(days=days)

            from sqlalchemy import select as sa_select
            result_rev = await session.execute(
                sa_select(func.sum(Purchase.amount_paid)).where(
                    Purchase.status == "approved",
                    Purchase.approved_at >= since
                )
            )
            revenue = result_rev.scalar_one() or 0

            result_sales = await session.execute(
                sa_select(func.count()).select_from(Purchase).where(
                    Purchase.status == "approved",
                    Purchase.approved_at >= since
                )
            )
            sales = result_sales.scalar_one()

            result_new_users = await session.execute(
                sa_select(func.count()).select_from(UserModel).where(UserModel.registered_at >= since)
            )
            new_users = result_new_users.scalar_one()

            period_text = f"Oxirgi {days} kun"
        else:
            revenue = await get_total_revenue(session)
            sales = await get_total_sales_count(session)
            new_users = await get_users_count(session)
            period_text = "Barcha vaqt"

    text = (
        f"📊 <b>Statistika: {period_text}</b>\n\n"
        f"👥 Yangi foydalanuvchilar: <b>{new_users:,}</b>\n"
        f"🛒 Sotilgan kurslar: <b>{sales:,}</b>\n"
        f"💰 Daromad: <b>{format_money(revenue)}</b>"
    )

    await call.message.edit_text(text, reply_markup=stats_filter_kb(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "export_excel")
async def export_excel(call: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await call.answer("⏳ Excel tayyorlanmoqda...")

    async with async_session() as session:
        buf = await export_to_excel(session)

    filename = f"bot_statistics_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.xlsx"
    await call.message.answer_document(
        BufferedInputFile(buf.read(), filename=filename),
        caption="📥 Bot statistikasi Excel formatida"
    )
