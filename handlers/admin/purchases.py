import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import RECEIPTS_CHANNEL_ID
from database.engine import async_session
from database.crud import (
    get_pending_groups, approve_group_atomic, reject_group,
    get_user, add_admin_log,
    get_referral_by_referral_id, mark_referral_bought,
    update_balance, get_referral_bonus, get_purchases_by_group
)
from database.models import User, Course
from keyboards.admin_kb import purchase_moderate_kb
from states import PurchaseStates
from utils.helpers import is_admin, format_money

logger = logging.getLogger(__name__)
router = Router(name="admin_purchases")


@router.message(F.text == "✅ To'lovlar")
async def show_pending_purchases(message: Message, db_user: User):
    if not is_admin(db_user):
        return

    async with async_session() as session:
        groups = await get_pending_groups(session)

    if not groups:
        await message.answer("✅ Hozircha tekshirilmagan to'lovlar yo'q.")
        return

    await message.answer(
        f"📋 <b>Kutayotgan to'lovlar: {len(groups)} ta guruh</b>",
        parse_mode="HTML"
    )

    async with async_session() as session:
        for g in groups:
            user = await get_user(session, g["user_id"])
            user_name = user.full_name if user else str(g["user_id"])
            uname = f"@{user.username}" if (user and user.username) else "yo'q"
            uid = g["user_id"]
            courses_text = "\n".join(f"  • {t}" for _, t in g["courses"])

            text = (
                f"🆔 Guruh: <code>{g['group_id']}</code>\n"
                f"👤 <a href='tg://user?id={uid}'>{user_name}</a> ({uname})\n"
                f"📚 Kurslar ({g['course_count']} ta):\n{courses_text}\n"
                f"💰 Summa: <b>{format_money(g['total_paid'])}</b>\n"
                f"🕐 {g['created_at'].strftime('%Y-%m-%d %H:%M')}"
            )
            try:
                await message.answer_photo(
                    g["receipt_photo"], caption=text,
                    reply_markup=purchase_moderate_kb(g["group_id"]),
                    parse_mode="HTML"
                )
            except Exception:
                await message.answer(
                    text,
                    reply_markup=purchase_moderate_kb(g["group_id"]),
                    parse_mode="HTML"
                )


@router.callback_query(F.data.startswith("approve_purchase:"))
async def approve_purchase_cb(call: CallbackQuery, db_user: User, bot: Bot):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    group_id = call.data.split(":", 1)[1]

    # ── Barcha ma'lumotlarni session ichida olamiz ──────────────
    user_id      = None
    total_paid   = 0
    course_data  = []
    bonus        = 0
    referrer_tg_id = None

    async with async_session() as session:
        # Atomik tasdiqlash
        approved = await approve_group_atomic(session, group_id, db_user.tg_id)
        if not approved:
            await call.answer("Allaqachon tasdiqlangan yoki topilmadi!", show_alert=True)
            try:
                await call.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return

        # Purchase larni olish
        purchases = await get_purchases_by_group(session, group_id)
        if not purchases:
            await call.answer("Topilmadi!", show_alert=True)
            return

        user_id    = purchases[0].user_id
        total_paid = sum(p.amount_paid for p in purchases)

        # Har bir kurs uchun ma'lumot — session ichida string sifatida olamiz
        for p in purchases:
            c_res = await session.execute(
                select(Course).where(Course.id == p.course_id)
            )
            c = c_res.scalar_one_or_none()
            course_data.append({
                "purchase_id":  p.id,
                "title":        c.title        if c else "Kurs",
                "channel_id":   c.channel_id   if c else None,
                "channel_link": c.channel_link if c else None,
            })

        # Referal bonusi — bir marta
        referral = await get_referral_by_referral_id(session, user_id)
        if referral and not referral.is_bought:
            bonus = await get_referral_bonus(session)
            await mark_referral_bought(session, user_id, bonus)
            await update_balance(session, referral.referrer_id, bonus)
            referrer_tg_id = referral.referrer_id

        await add_admin_log(
            session, db_user.tg_id,
            f"Guruh tasdiqlandi: {group_id} ({len(purchases)} ta kurs, {format_money(total_paid)})",
            None, "purchase"
        )

    # ── Session yopildi, faqat plain qiymatlar ishlatamiz ──────

    # Referal bonusi xabari
    if referrer_tg_id and bonus:
        try:
            await bot.send_message(
                referrer_tg_id,
                f"🎉 <b>Bonus!</b>\n\n"
                f"Do'stingiz kurs sotib oldi!\n"
                f"💰 Balansingizga <b>{format_money(bonus)}</b> yozildi!",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Referral bonus xabar yuborishda xato: {e}")

    # ── Maxfiy kanalga chekni yuborish ─────────────────────────
    if RECEIPTS_CHANNEL_ID:
        try:
            uname_str = f"@{db_user.username}" if db_user.username else f"ID:{user_id}"
            courses_list_ch = "\n".join(f"  • {cd['title']}" for cd in course_data)
            channel_caption = (
                f"✅ <b>Tasdiqlangan to'lov</b>\n\n"
                f"👤 {db_user.full_name} ({uname_str})\n"
                f"🆔 <code>{user_id}</code>\n"
                f"📚 Kurslar:\n{courses_list_ch}\n"
                f"💰 Summa: <b>{format_money(total_paid)}</b>\n"
                f"🕐 Admin: @{db_user.username or db_user.tg_id}"
            )
            # receipt_photo ni purchase dan olish
            async with async_session() as session:
                purchases_ch = await get_purchases_by_group(session, group_id)
                receipt = purchases_ch[0].receipt_photo if purchases_ch else None

            if receipt:
                await bot.send_photo(
                    RECEIPTS_CHANNEL_ID,
                    photo=receipt,
                    caption=channel_caption,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    RECEIPTS_CHANNEL_ID,
                    channel_caption,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.warning(f"Kanalga chek yuborishda xato: {e}")

    # Foydalanuvchiga tasdiqlash xabari
    try:
        courses_list = "\n".join(f"  📖 {cd['title']}" for cd in course_data)
        await bot.send_message(
            user_id,
            f"✅ <b>To'lovingiz tasdiqlandi!</b>\n\n"
            f"💰 Jami: <b>{format_money(total_paid)}</b>\n\n"
            f"📚 <b>Kurslaringiz:</b>\n{courses_list}\n\n"
            f"Quyida har bir kurs uchun kanal havolasi yuboriladi 👇",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Tasdiqlash xabari yuborishda xato uid={user_id}: {e}")

    # Har bir kurs uchun alohida invite link
    for cd in course_data:
        link_text = f"🎓 <b>{cd['title']}</b>\n\n"
        if cd["channel_id"]:
            try:
                invite = await bot.create_chat_invite_link(
                    cd["channel_id"],
                    member_limit=1,
                    name=f"P{cd['purchase_id']}"
                )
                link_text += (
                    f"🔗 Kanalga kirish havolasi:\n"
                    f"{invite.invite_link}\n\n"
                    f"⚠️ <i>Bu havola faqat bir marta ishlatiladi!</i>"
                )
            except Exception as e:
                logger.warning(f"Invite link yaratishda xato channel={cd['channel_id']}: {e}")
                link = cd["channel_link"] or "Admin bilan bogʻlaning"
                link_text += f"🔗 Kanal: {link}"
        elif cd["channel_link"]:
            link_text += f"🔗 Kanal: {cd['channel_link']}"
        else:
            link_text += "🔗 Kanal havolasi tez orada yuboriladi. Admin bilan bogʻlaning."

        try:
            await bot.send_message(user_id, link_text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Kanal havolasi yuborishda xato uid={user_id}: {e}")

    # Admin xabarini yangilash
    admin_name = f"@{db_user.username}" if db_user.username else str(db_user.tg_id)
    try:
        if call.message.caption is not None:
            old = call.message.caption or ""
            await call.message.edit_caption(
                caption=old + f"\n\n✅ Tasdiqlandi — {admin_name}",
                parse_mode="HTML"
            )
        else:
            old = call.message.text or ""
            await call.message.edit_text(
                old + f"\n\n✅ Tasdiqlandi — {admin_name}",
                parse_mode="HTML"
            )
    except Exception:
        pass

    await call.answer("✅ Tasdiqlandi! Foydalanuvchiga kanal havolalari yuborildi.")


@router.callback_query(F.data.startswith("reject_purchase:"))
async def reject_purchase_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    group_id = call.data.split(":", 1)[1]

    async with async_session() as session:
        purchases = await get_purchases_by_group(session, group_id)

    if not purchases or purchases[0].status != "pending":
        await call.answer("Allaqachon qayta ishlangan!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    user_id = purchases[0].user_id
    await state.update_data(reject_group_id=group_id, reject_user_id=user_id)
    await call.message.answer("❌ Rad etish sababini yozing:")
    await state.set_state(PurchaseStates.waiting_for_reject_reason)
    await call.answer()


@router.message(PurchaseStates.waiting_for_reject_reason)
async def process_reject_reason(message: Message, state: FSMContext, db_user: User, bot: Bot):
    if not is_admin(db_user):
        await state.clear()
        return

    reason = message.text.strip()
    data = await state.get_data()
    group_id = data.get("reject_group_id")
    user_id  = data.get("reject_user_id")

    if not group_id:
        await state.clear()
        return

    async with async_session() as session:
        await reject_group(session, group_id, db_user.tg_id, reason)
        await add_admin_log(
            session, db_user.tg_id,
            f"Rad etildi: {group_id}. Sabab: {reason}",
            None, "purchase"
        )

    try:
        await bot.send_message(
            user_id,
            f"❌ <b>To'lovingiz rad etildi</b>\n\n"
            f"Sabab: <i>{reason}</i>\n\n"
            f"Qayta to'lov qilib chek yuboring yoki admin bilan bog'laning.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Rad etish xabari yuborishda xato uid={user_id}: {e}")

    await message.answer("✅ Rad etildi. Foydalanuvchiga xabar yuborildi.")
    await state.clear()
