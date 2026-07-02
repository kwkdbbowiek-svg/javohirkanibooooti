import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, desc

from database.models import (
    User, Course, Purchase, CourseBundle, Referral, Withdrawal,
    AdminLog, PaymentCard, SupportTicket, SponsorChannel, BotSettings
)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================
# USER
# ============================================================

async def get_user(session: AsyncSession, tg_id: int) -> User | None:
    r = await session.execute(select(User).where(User.tg_id == tg_id))
    return r.scalar_one_or_none()


async def get_or_create_user(session: AsyncSession, tg_id: int,
                              username: str | None, full_name: str,
                              referer_id: int | None = None) -> tuple[User, bool]:
    user = await get_user(session, tg_id)
    if user:
        if user.username != username or user.full_name != full_name:
            user.username = username
            user.full_name = full_name
            await session.commit()
        return user, False
    if referer_id:
        ref = await get_user(session, referer_id)
        if not ref:
            referer_id = None
    try:
        user = User(tg_id=tg_id, username=username,
                    full_name=full_name, referer_id=referer_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user, True
    except Exception:
        await session.rollback()
        user = await get_user(session, tg_id)
        if user:
            return user, False
        raise


async def get_all_users_ids(session: AsyncSession) -> list[int]:
    r = await session.execute(
        select(User.tg_id).where(User.role == "user", User.is_blocked == False)
    )
    return list(r.scalars().all())


async def get_users_count(session: AsyncSession) -> int:
    r = await session.execute(select(func.count()).select_from(User))
    return r.scalar_one()


async def get_today_users_count(session: AsyncSession) -> int:
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    r = await session.execute(
        select(func.count()).select_from(User).where(User.registered_at >= today)
    )
    return r.scalar_one()


async def block_user(session: AsyncSession, tg_id: int, blocked: bool = True):
    await session.execute(update(User).where(User.tg_id == tg_id).values(is_blocked=blocked))
    await session.commit()


async def set_user_role(session: AsyncSession, tg_id: int, role: str):
    await session.execute(update(User).where(User.tg_id == tg_id).values(role=role))
    await session.commit()


async def update_balance(session: AsyncSession, tg_id: int, amount: int):
    await session.execute(
        update(User).where(User.tg_id == tg_id).values(balance=User.balance + amount)
    )
    await session.commit()


async def get_admins(session: AsyncSession) -> list[User]:
    r = await session.execute(
        select(User).where(User.role.in_(["moderator", "superadmin"]))
    )
    return list(r.scalars().all())


# ============================================================
# COURSE
# ============================================================

async def create_course(session: AsyncSession, title: str, description: str | None,
                        price: int, media_id: str | None, media_type: str | None,
                        channel_link: str | None, channel_id: int | None) -> Course:
    c = Course(title=title, description=description, price=price,
               media_id=media_id, media_type=media_type,
               channel_link=channel_link, channel_id=channel_id)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def get_course(session: AsyncSession, course_id: int) -> Course | None:
    r = await session.execute(
        select(Course).where(Course.id == course_id, Course.is_deleted == False)
    )
    return r.scalar_one_or_none()


async def get_active_courses(session: AsyncSession) -> list[Course]:
    r = await session.execute(
        select(Course).where(Course.is_active == True, Course.is_deleted == False)
    )
    return list(r.scalars().all())


async def get_all_courses(session: AsyncSession) -> list[Course]:
    r = await session.execute(select(Course).where(Course.is_deleted == False))
    return list(r.scalars().all())


async def update_course(session: AsyncSession, course_id: int, **kwargs):
    await session.execute(update(Course).where(Course.id == course_id).values(**kwargs))
    await session.commit()


async def soft_delete_course(session: AsyncSession, course_id: int):
    await session.execute(
        update(Course).where(Course.id == course_id).values(is_deleted=True, is_active=False)
    )
    await session.commit()


# ============================================================
# COURSE BUNDLE (chegirma)
# ============================================================

async def get_bundles(session: AsyncSession) -> list[CourseBundle]:
    r = await session.execute(
        select(CourseBundle).where(CourseBundle.is_active == True)
        .order_by(CourseBundle.course_count)
    )
    return list(r.scalars().all())


async def get_all_bundles(session: AsyncSession) -> list[CourseBundle]:
    r = await session.execute(select(CourseBundle).order_by(CourseBundle.course_count))
    return list(r.scalars().all())


async def get_bundle_by_count(session: AsyncSession, count: int) -> CourseBundle | None:
    r = await session.execute(
        select(CourseBundle).where(
            CourseBundle.course_count == count,
            CourseBundle.is_active == True
        )
    )
    return r.scalar_one_or_none()


async def create_bundle(session: AsyncSession, course_count: int,
                        bundle_price: int, description: str | None) -> CourseBundle:
    # Agar mavjud bo'lsa — yangilash
    existing = await session.execute(
        select(CourseBundle).where(CourseBundle.course_count == course_count)
    )
    b = existing.scalar_one_or_none()
    if b:
        b.bundle_price = bundle_price
        b.description = description
        b.is_active = True
        await session.commit()
        return b
    b = CourseBundle(course_count=course_count, bundle_price=bundle_price,
                     description=description)
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b


async def delete_bundle(session: AsyncSession, bundle_id: int):
    await session.execute(
        update(CourseBundle).where(CourseBundle.id == bundle_id).values(is_active=False)
    )
    await session.commit()


async def calculate_price(session: AsyncSession, course_ids: list[int]) -> tuple[int, int, int | None]:
    """
    Qaytaradi: (original_price, final_price, bundle_id_or_None)
    """
    courses = []
    for cid in course_ids:
        c = await get_course(session, cid)
        if c:
            courses.append(c)

    original = sum(c.price for c in courses)
    count = len(course_ids)

    bundle = await get_bundle_by_count(session, count)
    if bundle:
        return original, bundle.bundle_price, bundle.id

    return original, original, None


# ============================================================
# PURCHASE
# ============================================================

async def create_purchases_group(session: AsyncSession, user_id: int,
                                  course_ids: list[int], receipt_photo: str,
                                  amount_paid: int, original_price: int) -> str:
    """
    Bir nechta kurs uchun bitta group_id ostida Purchase yaratadi.
    Qaytaradi: group_id
    """
    group_id = str(uuid.uuid4())[:16]
    per_course = amount_paid // len(course_ids)

    for i, course_id in enumerate(course_ids):
        # Oxirgi kursga qoldiq
        paid = per_course if i < len(course_ids) - 1 else amount_paid - per_course * i
        orig = 0
        c = await get_course(session, course_id)
        if c:
            orig = c.price
        p = Purchase(
            user_id=user_id,
            course_id=course_id,
            group_id=group_id,
            status="pending",
            receipt_photo=receipt_photo,
            amount_paid=paid,
            original_price=orig,
        )
        session.add(p)

    await session.commit()
    return group_id


async def get_purchases_by_group(session: AsyncSession, group_id: str) -> list[Purchase]:
    r = await session.execute(
        select(Purchase).where(Purchase.group_id == group_id)
    )
    return list(r.scalars().all())


async def approve_group_atomic(session: AsyncSession, group_id: str, admin_id: int) -> bool:
    """Atomik — faqat 'pending' bo'lsa ishlaydi. True = OK, False = allaqachon bajarilgan."""
    r = await session.execute(
        update(Purchase)
        .where(Purchase.group_id == group_id, Purchase.status == "pending")
        .values(status="approved", approved_by_admin_id=admin_id, approved_at=_now())
        .returning(Purchase.id)
    )
    await session.commit()
    # RETURNING bir nechta qator (bir nechta kurs) qaytaradi — fetchall ishlatamiz
    rows = r.fetchall()
    return len(rows) > 0


async def reject_group(session: AsyncSession, group_id: str,
                       admin_id: int, reason: str):
    await session.execute(
        update(Purchase)
        .where(Purchase.group_id == group_id, Purchase.status == "pending")
        .values(status="rejected", approved_by_admin_id=admin_id, reject_reason=reason)
    )
    await session.commit()


async def get_pending_groups(session: AsyncSession) -> list[dict]:
    """
    Pending purchase larni group bo'yicha guruhlaydi.
    """
    r = await session.execute(
        select(
            Purchase.group_id,
            Purchase.user_id,
            Purchase.receipt_photo,
            Purchase.created_at,
            func.sum(Purchase.amount_paid).label("total_paid"),
            func.count(Purchase.id).label("course_count"),
        )
        .where(Purchase.status == "pending")
        .group_by(Purchase.group_id, Purchase.user_id,
                  Purchase.receipt_photo, Purchase.created_at)
        .order_by(Purchase.created_at)
    )
    rows = r.all()
    result = []
    for row in rows:
        # Kurs IDlarini olish
        courses_r = await session.execute(
            select(Purchase.course_id, Course.title)
            .join(Course, Course.id == Purchase.course_id)
            .where(Purchase.group_id == row.group_id)
        )
        course_list = [(c[0], c[1]) for c in courses_r.all()]
        result.append({
            "group_id":     row.group_id,
            "user_id":      row.user_id,
            "receipt_photo": row.receipt_photo,
            "created_at":   row.created_at,
            "total_paid":   row.total_paid,
            "course_count": row.course_count,
            "courses":      course_list,
        })
    return result


async def has_purchased(session: AsyncSession, user_id: int, course_id: int) -> bool:
    r = await session.execute(
        select(Purchase.id).where(
            Purchase.user_id == user_id,
            Purchase.course_id == course_id,
            Purchase.status == "approved"
        )
    )
    return r.scalar_one_or_none() is not None


async def has_pending_for_courses(session: AsyncSession, user_id: int,
                                   course_ids: list[int]) -> bool:
    """Ushbu kurslardan biri uchun pending bor-yo'qligini tekshiradi"""
    r = await session.execute(
        select(Purchase.id).where(
            Purchase.user_id == user_id,
            Purchase.course_id.in_(course_ids),
            Purchase.status == "pending"
        )
    )
    return r.scalar_one_or_none() is not None


async def get_user_purchases(session: AsyncSession, user_id: int) -> list[Purchase]:
    r = await session.execute(
        select(Purchase).where(
            Purchase.user_id == user_id,
            Purchase.status == "approved"
        )
    )
    return list(r.scalars().all())


async def get_total_revenue(session: AsyncSession) -> int:
    r = await session.execute(
        select(func.sum(Purchase.amount_paid)).where(Purchase.status == "approved")
    )
    return r.scalar_one() or 0


async def get_today_revenue(session: AsyncSession) -> int:
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    r = await session.execute(
        select(func.sum(Purchase.amount_paid)).where(
            Purchase.status == "approved", Purchase.approved_at >= today
        )
    )
    return r.scalar_one() or 0


async def get_buyers_count(session: AsyncSession) -> int:
    r = await session.execute(
        select(func.count(func.distinct(Purchase.user_id))).where(Purchase.status == "approved")
    )
    return r.scalar_one()


async def get_today_buyers_count(session: AsyncSession) -> int:
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    r = await session.execute(
        select(func.count(func.distinct(Purchase.user_id))).where(
            Purchase.status == "approved", Purchase.approved_at >= today
        )
    )
    return r.scalar_one()


async def get_total_sales_count(session: AsyncSession) -> int:
    r = await session.execute(
        select(func.count()).select_from(Purchase).where(Purchase.status == "approved")
    )
    return r.scalar_one()


async def get_top_course(session: AsyncSession) -> tuple[str, int] | None:
    r = await session.execute(
        select(Course.title, func.count(Purchase.id).label("cnt"))
        .join(Purchase, Purchase.course_id == Course.id)
        .where(Purchase.status == "approved")
        .group_by(Course.title)
        .order_by(desc("cnt"))
        .limit(1)
    )
    row = r.first()
    return (row[0], row[1]) if row else None


async def get_purchases_for_rating_reminder(session: AsyncSession) -> list[Purchase]:
    from datetime import timedelta
    threshold = _now() - timedelta(hours=24)
    r = await session.execute(
        select(Purchase).where(
            Purchase.status == "approved",
            Purchase.rating_reminded == False,
            Purchase.rating == None,
            Purchase.approved_at <= threshold
        )
    )
    return list(r.scalars().all())


async def get_abandoned_cart_users(session: AsyncSession) -> list[Purchase]:
    from datetime import timedelta
    threshold = _now() - timedelta(hours=2)
    r = await session.execute(
        select(Purchase).where(
            Purchase.status == "pending",
            Purchase.created_at <= threshold
        )
    )
    return list(r.scalars().all())


# ============================================================
# PAYMENT CARD
# ============================================================

async def get_payment_cards(session: AsyncSession) -> list[PaymentCard]:
    r = await session.execute(select(PaymentCard).where(PaymentCard.is_active == True))
    return list(r.scalars().all())


async def add_payment_card(session: AsyncSession, card_number: str, holder_name: str,
                           bank_name: str, card_type: str, is_default: bool = False) -> PaymentCard:
    if is_default:
        await session.execute(update(PaymentCard).values(is_default=False))
    c = PaymentCard(card_number=card_number, holder_name=holder_name,
                    bank_name=bank_name, card_type=card_type, is_default=is_default)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def set_default_card(session: AsyncSession, card_id: int):
    await session.execute(update(PaymentCard).values(is_default=False))
    await session.execute(update(PaymentCard).where(PaymentCard.id == card_id).values(is_default=True))
    await session.commit()


async def delete_payment_card(session: AsyncSession, card_id: int):
    await session.execute(update(PaymentCard).where(PaymentCard.id == card_id).values(is_active=False))
    await session.commit()


# ============================================================
# REFERRAL
# ============================================================

async def create_referral(session: AsyncSession, referrer_id: int, referral_id: int) -> bool:
    try:
        ref = Referral(referrer_id=referrer_id, referral_id=referral_id)
        session.add(ref)
        await session.commit()
        return True
    except Exception:
        await session.rollback()
        return False


async def get_referral_by_referral_id(session: AsyncSession, referral_id: int) -> Referral | None:
    r = await session.execute(select(Referral).where(Referral.referral_id == referral_id))
    return r.scalar_one_or_none()


async def mark_referral_bought(session: AsyncSession, referral_id: int, bonus: int):
    await session.execute(
        update(Referral).where(Referral.referral_id == referral_id)
        .values(is_bought=True, bonus_earned=bonus)
    )
    await session.commit()


async def get_referral_stats(session: AsyncSession, referrer_id: int) -> dict:
    total = (await session.execute(
        select(func.count()).select_from(Referral).where(Referral.referrer_id == referrer_id)
    )).scalar_one()
    bought = (await session.execute(
        select(func.count()).select_from(Referral).where(
            Referral.referrer_id == referrer_id, Referral.is_bought == True)
    )).scalar_one()
    bonus_total = (await session.execute(
        select(func.sum(Referral.bonus_earned)).where(Referral.referrer_id == referrer_id)
    )).scalar_one() or 0
    return {"total": total, "bought": bought, "bonus_total": bonus_total}


# ============================================================
# WITHDRAWAL
# ============================================================

async def create_withdrawal(session: AsyncSession, user_id: int, card_number: str,
                            card_holder: str, amount: int) -> Withdrawal:
    w = Withdrawal(user_id=user_id, card_number=card_number,
                   card_holder=card_holder, amount=amount)
    session.add(w)
    await session.execute(
        update(User).where(User.tg_id == user_id).values(balance=User.balance - amount)
    )
    await session.commit()
    await session.refresh(w)
    return w


async def get_pending_withdrawals(session: AsyncSession) -> list[Withdrawal]:
    r = await session.execute(
        select(Withdrawal).where(Withdrawal.status == "pending").order_by(Withdrawal.created_at)
    )
    return list(r.scalars().all())


async def approve_withdrawal(session: AsyncSession, withdrawal_id: int, admin_id: int):
    r = await session.execute(select(Withdrawal).where(Withdrawal.id == withdrawal_id))
    w = r.scalar_one_or_none()
    if not w:
        return
    await session.execute(
        update(Withdrawal).where(Withdrawal.id == withdrawal_id)
        .values(status="paid", admin_id=admin_id, processed_at=_now())
    )
    await session.execute(
        update(User).where(User.tg_id == w.user_id).values(withdrawn=User.withdrawn + w.amount)
    )
    await session.commit()


async def reject_withdrawal(session: AsyncSession, withdrawal_id: int, admin_id: int):
    r = await session.execute(select(Withdrawal).where(Withdrawal.id == withdrawal_id))
    w = r.scalar_one_or_none()
    if not w:
        return
    await session.execute(
        update(Withdrawal).where(Withdrawal.id == withdrawal_id)
        .values(status="rejected", admin_id=admin_id, processed_at=_now())
    )
    await session.execute(
        update(User).where(User.tg_id == w.user_id).values(balance=User.balance + w.amount)
    )
    await session.commit()


# ============================================================
# ADMIN LOG
# ============================================================

async def add_admin_log(session: AsyncSession, admin_id: int, action: str,
                        target_id: int | None = None, target_type: str | None = None):
    log = AdminLog(admin_id=admin_id, action=action,
                   target_id=target_id, target_type=target_type)
    session.add(log)
    await session.commit()


async def get_admin_logs(session: AsyncSession, limit: int = 50) -> list[AdminLog]:
    r = await session.execute(
        select(AdminLog).order_by(AdminLog.timestamp.desc()).limit(limit)
    )
    return list(r.scalars().all())


# ============================================================
# SPONSOR CHANNEL
# ============================================================

async def get_sponsor_channels(session: AsyncSession) -> list[SponsorChannel]:
    r = await session.execute(select(SponsorChannel).where(SponsorChannel.is_active == True))
    return list(r.scalars().all())


async def add_sponsor_channel(session: AsyncSession, channel_id: int,
                               channel_name: str, channel_link: str) -> SponsorChannel:
    ch = SponsorChannel(channel_id=channel_id, channel_name=channel_name, channel_link=channel_link)
    session.add(ch)
    await session.commit()
    await session.refresh(ch)
    return ch


async def remove_sponsor_channel(session: AsyncSession, channel_id: int):
    await session.execute(
        update(SponsorChannel).where(SponsorChannel.channel_id == channel_id).values(is_active=False)
    )
    await session.commit()


# ============================================================
# SUPPORT TICKET
# ============================================================

async def create_support_ticket(session: AsyncSession, user_id: int,
                                 message_id: int, text: str) -> SupportTicket:
    t = SupportTicket(user_id=user_id, message_id=message_id, text=text)
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


async def get_open_tickets(session: AsyncSession) -> list[SupportTicket]:
    r = await session.execute(select(SupportTicket).where(SupportTicket.status == "open"))
    return list(r.scalars().all())


async def close_ticket(session: AsyncSession, ticket_id: int):
    await session.execute(
        update(SupportTicket).where(SupportTicket.id == ticket_id).values(status="closed")
    )
    await session.commit()


# ============================================================
# BOT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {
    "referral_bonus": ("20000", "Referal bonus summasi (so'm)"),
    "min_withdrawal":  ("50000", "Minimal pul yechish summasi (so'm)"),
    "faq_text": (
        "ℹ️ <b>Kurslar haqida ma'lumot</b>\n\nAdmin panel orqali FAQ matnini o'zgartiring.",
        "FAQ matni"
    ),
    "shop_header_text": (
        "📚 <b>Kurslarni tanlang:</b>\n\n"
        "Bir yoki bir nechta kursni tanlashingiz mumkin.\n"
        "Tanlash uchun kurs nomiga bosing, so'ng 🛒 Sotib olish tugmasini bosing.",
        "Kurs tanlash sahifasidagi matn (admin o'zgartira oladi)"
    ),
}


async def get_setting(session: AsyncSession, key: str) -> str | None:
    r = await session.execute(select(BotSettings).where(BotSettings.key == key))
    row = r.scalar_one_or_none()
    return row.value if row else DEFAULT_SETTINGS.get(key, (None,))[0]


async def set_setting(session: AsyncSession, key: str, value: str):
    r = await session.execute(select(BotSettings).where(BotSettings.key == key))
    row = r.scalar_one_or_none()
    if row:
        row.value = value
        row.updated_at = _now()
    else:
        desc = DEFAULT_SETTINGS.get(key, ("", ""))[1]
        row = BotSettings(key=key, value=value, description=desc)
        session.add(row)
    await session.commit()


async def get_all_settings(session: AsyncSession) -> dict:
    r = await session.execute(select(BotSettings))
    data = {k: v for k, (v, _) in DEFAULT_SETTINGS.items()}
    for row in r.scalars().all():
        data[row.key] = row.value
    return data


async def get_referral_bonus(session: AsyncSession) -> int:
    val = await get_setting(session, "referral_bonus")
    try:
        return int(val)
    except Exception:
        return 20000


async def get_min_withdrawal(session: AsyncSession) -> int:
    val = await get_setting(session, "min_withdrawal")
    try:
        return int(val)
    except Exception:
        return 50000


async def get_faq_text(session: AsyncSession) -> str:
    val = await get_setting(session, "faq_text")
    return val or "ℹ️ FAQ hali sozlanmagan."


async def get_shop_header_text(session: AsyncSession) -> str:
    val = await get_setting(session, "shop_header_text")
    return val or "📚 <b>Kurslarni tanlang:</b>"
