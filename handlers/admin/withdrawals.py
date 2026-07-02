import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select

from database.engine import async_session
from database.crud import (
    get_pending_withdrawals, approve_withdrawal,
    reject_withdrawal, add_admin_log, get_user
)
from database.models import Withdrawal
from keyboards.admin_kb import withdrawal_moderate_kb
from utils.helpers import is_admin, format_money

logger = logging.getLogger(__name__)
router = Router(name="admin_withdrawals")


class WithdrawalAdminStates(StatesGroup):
    waiting_for_receipt = State()


# ────────────────────────────────────────────────────────────
# Kutayotgan so'rovlar ro'yxati
# ────────────────────────────────────────────────────────────

@router.message(F.text == "💸 Yechish so'rovlari")
async def show_pending_withdrawals(message: Message, db_user):
    if not is_admin(db_user):
        return

    async with async_session() as session:
        withdrawals = await get_pending_withdrawals(session)

    if not withdrawals:
        await message.answer("✅ Hozircha kutayotgan yechish so'rovlari yo'q.")
        return

    await message.answer(
        f"💸 <b>Kutayotgan so'rovlar: {len(withdrawals)} ta</b>",
        parse_mode="HTML"
    )

    async with async_session() as session:
        for w in withdrawals:
            user = await get_user(session, w.user_id)
            uname     = f"@{user.username}" if (user and user.username) else "yo'q"
            user_name = user.full_name if user else str(w.user_id)

            # Barcha qiymatlarni session ichida skalar sifatida olamiz
            w_id     = w.id
            w_uid    = w.user_id
            w_card   = w.card_number
            w_holder = w.card_holder or "—"
            w_amount = w.amount
            w_date   = w.created_at.strftime("%Y-%m-%d %H:%M")

            text = (
                f"💸 <b>Yechish so'rovi #{w_id}</b>\n\n"
                f"👤 <a href='tg://user?id={w_uid}'>{user_name}</a> ({uname})\n"
                f"🆔 ID: <code>{w_uid}</code>\n"
                f"💳 Karta: <code>{w_card}</code>\n"
                f"👤 Egasi: <b>{w_holder}</b>\n"
                f"💰 Summa: <b>{format_money(w_amount)}</b>\n"
                f"🕐 {w_date}"
            )
            await message.answer(
                text,
                reply_markup=withdrawal_moderate_kb(w_id),
                parse_mode="HTML"
            )


# ────────────────────────────────────────────────────────────
# Tasdiqlash — 1: Admin "To'landi" bosadi → chek so'raladi
# ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("approve_withdrawal:"))
async def approve_withdrawal_start(call: CallbackQuery, state: FSMContext, db_user):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    withdrawal_id = int(call.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        )
        w = result.scalar_one_or_none()

        if not w:
            await call.answer("So'rov topilmadi!", show_alert=True)
            return
        if w.status != "pending":
            await call.answer(f"Allaqachon: {w.status}", show_alert=True)
            try:
                await call.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return

        # Skalarlar
        user_id = w.user_id
        amount  = w.amount
        card    = w.card_number
        holder  = w.card_holder or "—"

    await state.update_data(
        aw_id=withdrawal_id,
        aw_user_id=user_id,
        aw_amount=amount,
        aw_card=card,
        aw_holder=holder
    )

    await call.message.answer(
        f"✅ <b>Pul o'tkazildi deb belgilash</b>\n\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{holder}</b>\n"
        f"💰 Summa: <b>{format_money(amount)}</b>\n\n"
        f"📸 Endi <b>to'lov cheki rasmini</b> yuboring "
        f"(foydalanuvchiga avtomatik yuboriladi).\n\n"
        f"Yoki /skip — rasisz tasdiqlash:",
        parse_mode="HTML"
    )
    await state.set_state(WithdrawalAdminStates.waiting_for_receipt)
    await call.answer()


# ────────────────────────────────────────────────────────────
# Tasdiqlash — 2: Chek rasm yuboriladi → foydalanuvchiga boradi
# ────────────────────────────────────────────────────────────

@router.message(WithdrawalAdminStates.waiting_for_receipt)
async def approve_withdrawal_receipt(message: Message, state: FSMContext, db_user, bot: Bot):
    if not is_admin(db_user):
        await state.clear()
        return

    data = await state.get_data()
    w_id    = data.get("aw_id")
    user_id = data.get("aw_user_id")
    amount  = data.get("aw_amount")
    card    = data.get("aw_card")

    if not w_id:
        await state.clear()
        return

    is_skip   = message.text and message.text.strip() == "/skip"
    has_photo = bool(message.photo)

    if not is_skip and not has_photo:
        await message.answer(
            "❌ Chek rasmini yuboring yoki /skip yozing:"
        )
        return

    # Bazada tasdiqlash
    async with async_session() as session:
        # Qayta tekshiruv — idempotency
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == w_id)
        )
        w = result.scalar_one_or_none()
        if not w or w.status != "pending":
            await message.answer("Bu so'rov allaqachon qayta ishlangan!")
            await state.clear()
            return

        await approve_withdrawal(session, w_id, db_user.tg_id)
        await add_admin_log(
            session, db_user.tg_id,
            f"Yechish tasdiqlandi #{w_id} — {format_money(amount)}",
            w_id, "withdrawal"
        )

    # Foydalanuvchiga xabar
    user_msg = (
        f"✅ <b>Pulingiz muvaffaqiyatli o'tkazildi!</b>\n\n"
        f"💰 Summa: <b>{format_money(amount)}</b>\n"
        f"💳 Karta: <code>{card}</code>\n\n"
        f"Balansingizdan ayirildi. Rahmat! 💙"
    )

    if has_photo:
        try:
            await bot.send_photo(
                user_id,
                photo=message.photo[-1].file_id,
                caption=user_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Chek rasm yuborishda xato uid={user_id}: {e}")
            try:
                await bot.send_message(user_id, user_msg, parse_mode="HTML")
            except Exception as e2:
                logger.warning(f"Xabar yuborishda xato uid={user_id}: {e2}")
    else:
        try:
            await bot.send_message(user_id, user_msg, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Xabar yuborishda xato uid={user_id}: {e}")

    admin_name = f"@{db_user.username}" if db_user.username else str(db_user.tg_id)
    await message.answer(
        f"✅ <b>So'rov #{w_id} tasdiqlandi!</b>\n"
        f"Foydalanuvchiga {'chek bilan ' if has_photo else ''}xabar yuborildi.",
        parse_mode="HTML"
    )
    await state.clear()


# ────────────────────────────────────────────────────────────
# Rad etish
# ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject_withdrawal:"))
async def reject_withdrawal_cb(call: CallbackQuery, db_user, bot: Bot):
    if not is_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    withdrawal_id = int(call.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        )
        w = result.scalar_one_or_none()

        if not w:
            await call.answer("So'rov topilmadi!", show_alert=True)
            return
        if w.status != "pending":
            await call.answer(f"Allaqachon: {w.status}", show_alert=True)
            try:
                await call.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return

        user_id = w.user_id
        amount  = w.amount

        await reject_withdrawal(session, withdrawal_id, db_user.tg_id)
        await add_admin_log(
            session, db_user.tg_id,
            f"Yechish rad etildi #{withdrawal_id} — {format_money(amount)}",
            withdrawal_id, "withdrawal"
        )

    # Foydalanuvchiga xabar — balans qaytarildi
    try:
        await bot.send_message(
            user_id,
            f"❌ <b>Pul yechish so'rovingiz bekor qilindi.</b>\n\n"
            f"💰 <b>{format_money(amount)}</b> balansingizga qaytarildi.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Rad etish xabari yuborishda xato uid={user_id}: {e}")

    admin_name = f"@{db_user.username}" if db_user.username else str(db_user.tg_id)
    try:
        await call.message.edit_text(
            (call.message.text or "") + f"\n\n❌ Bekor — {admin_name}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await call.answer("❌ Bekor qilindi, balans qaytarildi!")
