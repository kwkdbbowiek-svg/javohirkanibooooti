from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from database.models import Course, PaymentCard


def admin_main_kb(is_super: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📊 Statistika"))
    builder.row(KeyboardButton(text="✅ To'lovlar"), KeyboardButton(text="💸 Yechish so'rovlari"))
    if is_super:
        builder.row(KeyboardButton(text="📚 Kurslar"), KeyboardButton(text="💳 Kartalar"))
        builder.row(KeyboardButton(text="🎁 Chegirmalar"), KeyboardButton(text="📢 Homiy kanallar"))
        builder.row(KeyboardButton(text="📣 Broadcast"), KeyboardButton(text="👮 Adminlar"))
        builder.row(KeyboardButton(text="⚙️ Sozlamalar"))
    return builder.as_markup(resize_keyboard=True)


def purchase_moderate_kb(group_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_purchase:{group_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_purchase:{group_id}")
    )
    return builder.as_markup()


def withdrawal_moderate_kb(withdrawal_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ To'landi", callback_data=f"approve_withdrawal:{withdrawal_id}"),
        InlineKeyboardButton(text="❌ Bekor qilindi", callback_data=f"reject_withdrawal:{withdrawal_id}")
    )
    return builder.as_markup()


def courses_manage_kb(courses: list[Course]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in courses:
        status = "✅" if c.is_active else "🔴"
        builder.row(InlineKeyboardButton(
            text=f"{status} {c.title}",
            callback_data=f"admin_course:{c.id}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Yangi kurs qo'shish", callback_data="add_course"))
    return builder.as_markup()


def course_manage_detail_kb(course: Course) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "🔴 Noaktiv qilish" if course.is_active else "✅ Aktiv qilish"
    builder.row(InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_course:{course.id}"))
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_course:{course.id}"))
    builder.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_course:{course.id}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_courses_admin"))
    return builder.as_markup()


def course_edit_fields_kb(course_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Nomi", callback_data=f"edit_field:{course_id}:title"))
    builder.row(InlineKeyboardButton(text="📄 Tavsif", callback_data=f"edit_field:{course_id}:description"))
    builder.row(InlineKeyboardButton(text="💰 Narx", callback_data=f"edit_field:{course_id}:price"))
    builder.row(InlineKeyboardButton(text="🔗 Kanal havolasi", callback_data=f"edit_field:{course_id}:channel_link"))
    builder.row(InlineKeyboardButton(text="🖼 Media", callback_data=f"edit_field:{course_id}:media"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin_course:{course_id}"))
    return builder.as_markup()


def cards_manage_kb(cards: list[PaymentCard]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for card in cards:
        label = f"{'⭐ ' if card.is_default else ''}{card.bank_name} — {card.card_number[-4:]}"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"admin_card:{card.id}"))
    builder.row(InlineKeyboardButton(text="➕ Karta qo'shish", callback_data="add_card"))
    return builder.as_markup()


def card_manage_detail_kb(card: PaymentCard) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not card.is_default:
        builder.row(InlineKeyboardButton(text="⭐ Asosiy qilish", callback_data=f"set_default_card:{card.id}"))
    builder.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_card:{card.id}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_cards"))
    return builder.as_markup()


def confirm_delete_kb(action: str, item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_{action}:{item_id}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data=f"cancel_{action}")
    )
    return builder.as_markup()


def user_manage_kb(tg_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    block_text = "✅ Blokdan chiqarish" if is_blocked else "🚫 Bloklash"
    builder.row(InlineKeyboardButton(text=block_text, callback_data=f"toggle_block:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_users"))
    return builder.as_markup()


def export_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📥 Excel yuklab olish", callback_data="export_excel"))
    return builder.as_markup()


def stats_filter_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 7 kun", callback_data="stats_filter:7"),
        InlineKeyboardButton(text="📅 30 kun", callback_data="stats_filter:30"),
        InlineKeyboardButton(text="📅 Barchasi", callback_data="stats_filter:0")
    )
    builder.row(InlineKeyboardButton(text="📥 Excel", callback_data="export_excel"))
    return builder.as_markup()


def admin_roles_kb(admins: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for admin in admins:
        builder.row(InlineKeyboardButton(
            text=f"{'👑 ' if admin.role == 'superadmin' else '🛡 '}{admin.full_name} (@{admin.username or admin.tg_id})",
            callback_data=f"manage_admin:{admin.tg_id}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin"))
    return builder.as_markup()


def manage_admin_kb(tg_id: int, role: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if role == "moderator":
        builder.row(InlineKeyboardButton(text="👑 Super Admin qilish", callback_data=f"set_role:superadmin:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🗑 Adminlikdan olish", callback_data=f"remove_admin:{tg_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admins"))
    return builder.as_markup()


def sponsor_channels_kb(channels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.row(InlineKeyboardButton(
            text=f"📢 {ch.channel_name}",
            callback_data=f"del_sponsor:{ch.channel_id}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_sponsor_channel"))
    return builder.as_markup()


def support_reply_kb(user_id: int, ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Javob berish", callback_data=f"reply_ticket:{user_id}:{ticket_id}"))
    builder.row(InlineKeyboardButton(text="✅ Yopish", callback_data=f"close_ticket:{ticket_id}"))
    return builder.as_markup()


def settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Referal bonus", callback_data="edit_setting:referral_bonus"))
    builder.row(InlineKeyboardButton(text="💳 Minimal yechish", callback_data="edit_setting:min_withdrawal"))
    builder.row(InlineKeyboardButton(text="ℹ️ FAQ matnini tahrirlash", callback_data="edit_setting:faq_text"))
    builder.row(InlineKeyboardButton(text="📚 Kurs sahifasi matni", callback_data="edit_setting:shop_header_text"))
    return builder.as_markup()


def bundles_kb(bundles: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b in bundles:
        status = "✅" if b.is_active else "🔴"
        builder.row(InlineKeyboardButton(
            text=f"{status} {b.course_count} ta kurs — {b.bundle_price:,} so'm",
            callback_data=f"admin_bundle:{b.id}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Chegirma qo'shish", callback_data="add_bundle"))
    return builder.as_markup()


def bundle_detail_kb(bundle_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_bundle:{bundle_id}"))
    builder.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_bundle:{bundle_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_bundles"))
    return builder.as_markup()
