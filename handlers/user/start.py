from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database.models import User
from database.engine import async_session
from database.crud import create_referral, get_referral_by_referral_id
from keyboards.user_kb import main_menu_kb
from keyboards.admin_kb import admin_main_kb
from utils.helpers import is_admin, is_super_admin

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, is_new_user: bool):
    # Referal — FAQAT yangi foydalanuvchilar uchun
    parts = message.text.split()
    if is_new_user and len(parts) > 1 and parts[1].startswith("REF_"):
        try:
            referrer_id = int(parts[1].replace("REF_", ""))
            if referrer_id != message.from_user.id:
                async with async_session() as session:
                    existing = await get_referral_by_referral_id(
                        session, message.from_user.id
                    )
                    if not existing:
                        await create_referral(session, referrer_id,
                                              message.from_user.id)
        except Exception:
            pass

    if is_admin(db_user):
        await message.answer(
            f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n"
            f"🔐 <b>Admin Panel</b>",
            reply_markup=admin_main_kb(is_super=is_super_admin(db_user)),
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"👋 Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        f"📚 <b>Ingliz tili online kurslar botiga xush kelibsiz!</b>\n\n"
        f"Quyidagi menyu orqali kurslarni ko'rib chiqishingiz mumkin.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    if is_admin(db_user):
        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=admin_main_kb(is_super=is_super_admin(db_user))
        )
    else:
        await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_kb())
