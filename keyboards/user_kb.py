from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from database.models import Course, PaymentCard
from utils.helpers import format_money


def main_menu_kb() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📚 Kursni sotib olish"))
    b.row(KeyboardButton(text="ℹ️ Kurs haqida (FAQ)"))
    b.row(KeyboardButton(text="🎓 Mening kurslarim"), KeyboardButton(text="👥 Referal tizim"))
    return b.as_markup(resize_keyboard=True)


def courses_selection_kb(courses: list[Course],
                         selected_ids: list[int],
                         original_price: int,
                         final_price: int) -> InlineKeyboardMarkup:
    """
    Kurslarni tanlash tugmalari.
    Tanlangan kursda belgi bor, tanlanmaganda yo'q.
    Pastda narx bilan 'Sotib olish' tugmasi.
    """
    b = InlineKeyboardBuilder()
    for course in courses:
        is_selected = course.id in selected_ids
        prefix = "✅ " if is_selected else ""
        b.row(InlineKeyboardButton(
            text=f"{prefix}{course.title} — {format_money(course.price)}",
            callback_data=f"pick_course:{course.id}"
        ))

    if selected_ids:
        count = len(selected_ids)
        if original_price != final_price:
            btn_text = f"🛒 Sotib olish ({count} ta) — {format_money(final_price)}"
        else:
            btn_text = f"🛒 Sotib olish ({count} ta) — {format_money(final_price)}"

        b.row(InlineKeyboardButton(
            text=btn_text,
            callback_data="proceed_purchase"
        ))

    return b.as_markup()


def payment_cards_kb(cards: list[PaymentCard]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for card in cards:
        label = f"{'⭐ ' if card.is_default else ''}{card.bank_name} ({card.card_type}) — {card.card_number[-4:]}"
        b.row(InlineKeyboardButton(text=label, callback_data=f"select_card:{card.id}"))
    b.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_purchase"))
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_purchase"))
    return b.as_markup()


def my_courses_kb(purchases: list, courses_map: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    seen = set()
    for p in purchases:
        if p.course_id in seen:
            continue
        seen.add(p.course_id)
        course = courses_map.get(p.course_id)
        if course:
            b.row(InlineKeyboardButton(
                text=f"🎓 {course.title}",
                callback_data=f"my_course:{p.id}"
            ))
    return b.as_markup()


def course_link_kb(purchase_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔗 Kanalga kirish", callback_data=f"get_link:{purchase_id}"))
    return b.as_markup()


def rating_kb(purchase_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text="⭐" * i, callback_data=f"rate:{purchase_id}:{i}")
    b.adjust(5)
    return b.as_markup()


def withdrawal_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💳 Pul yechish", callback_data="withdraw_request"))
    return b.as_markup()


def subscribe_check_kb(channels: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.row(InlineKeyboardButton(text=f"📢 {ch.channel_name}", url=ch.channel_link))
    b.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription"))
    return b.as_markup()


def courses_kb(courses: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for course in courses:
        b.row(InlineKeyboardButton(
            text=f'📖 {course.title} — {format_money(course.price)}',
            callback_data=f'course_view:{course.id}'
        ))
    return b.as_markup()


def course_detail_kb(course_id: int, already_bought: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if already_bought:
        b.row(InlineKeyboardButton(text='✅ Sotib olingan', callback_data='already_bought'))
    else:
        b.row(InlineKeyboardButton(text='🛒 Sotib olish', callback_data=f'buy_course:{course_id}'))
    b.row(InlineKeyboardButton(text='🔙 Orqaga', callback_data='back_to_courses'))
    return b.as_markup()
