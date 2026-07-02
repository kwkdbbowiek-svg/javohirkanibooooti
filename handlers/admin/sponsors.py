from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.engine import async_session
from database.crud import (
    get_sponsor_channels, add_sponsor_channel,
    remove_sponsor_channel, add_admin_log
)
from database.models import User
from keyboards.admin_kb import sponsor_channels_kb
from states import AddSponsorStates
from utils.helpers import is_super_admin

router = Router(name="admin_sponsors")


@router.message(F.text == "📢 Homiy kanallar")
async def show_sponsors(message: Message, db_user: User):
    if not is_super_admin(db_user):
        return

    async with async_session() as session:
        channels = await get_sponsor_channels(session)

    text = f"📢 <b>Homiy kanallar ({len(channels)} ta):</b>\n\n"
    if channels:
        for ch in channels:
            text += f"• {ch.channel_name} — <code>{ch.channel_id}</code>\n"
    else:
        text += "Hozircha kanallar yo'q."

    await message.answer(
        text,
        reply_markup=sponsor_channels_kb(channels),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "add_sponsor_channel")
async def add_sponsor_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await call.message.answer(
        "📢 <b>Yangi homiy kanal qo'shish</b>\n\n"
        "Kanal <b>ID</b>sini kiriting (masalan: -1001234567890)\n\n"
        "<i>Bot kanalda admin bo'lishi shart!</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddSponsorStates.waiting_for_channel_id)
    await call.answer()


@router.message(AddSponsorStates.waiting_for_channel_id)
async def sponsor_channel_id_input(message: Message, state: FSMContext, bot: Bot):
    try:
        channel_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Kanal ID raqam bo'lishi kerak (masalan: -1001234567890):")
        return

    # Try to get channel info
    try:
        chat = await bot.get_chat(channel_id)
        channel_name = chat.title or f"Kanal {channel_id}"
        await state.update_data(channel_id=channel_id, channel_name=channel_name)
        await message.answer(
            f"✅ Kanal topildi: <b>{channel_name}</b>\n\n"
            f"Kanal havolasini kiriting (masalan: https://t.me/channel_name):",
            parse_mode="HTML"
        )
        await state.set_state(AddSponsorStates.waiting_for_channel_link)
    except Exception:
        await message.answer(
            "❌ Kanal topilmadi!\n\n"
            "Bot kanalda admin bo'lishi kerak.\n"
            "Kanal ID ni tekshirib qayta kiriting:"
        )


@router.message(AddSponsorStates.waiting_for_channel_link)
async def sponsor_channel_link_input(message: Message, state: FSMContext, db_user: User):
    link = message.text.strip()
    if not link.startswith("https://t.me/"):
        await message.answer("❌ To'g'ri havola kiriting (https://t.me/...):")
        return

    data = await state.get_data()

    async with async_session() as session:
        channel = await add_sponsor_channel(
            session,
            channel_id=data["channel_id"],
            channel_name=data["channel_name"],
            channel_link=link
        )
        await add_admin_log(
            session, db_user.tg_id,
            f"Homiy kanal qo'shildi: {data['channel_name']} ({data['channel_id']})",
            data["channel_id"], "sponsor"
        )

    await message.answer(
        f"✅ <b>Kanal qo'shildi!</b>\n\n"
        f"📢 {data['channel_name']}\n"
        f"🔗 {link}",
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("del_sponsor:"))
async def delete_sponsor(call: CallbackQuery, db_user: User):
    if not is_super_admin(db_user):
        await call.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    channel_id = int(call.data.split(":")[1])

    async with async_session() as session:
        await remove_sponsor_channel(session, channel_id)
        await add_admin_log(
            session, db_user.tg_id,
            f"Homiy kanal o'chirildi: {channel_id}",
            channel_id, "sponsor"
        )
        channels = await get_sponsor_channels(session)

    await call.answer("✅ Kanal o'chirildi!")
    await call.message.edit_text(
        f"📢 <b>Homiy kanallar ({len(channels)} ta):</b>",
        reply_markup=sponsor_channels_kb(channels),
        parse_mode="HTML"
    )
