from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, String, Text, Boolean, Integer,
    DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.engine import Base


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    referer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.tg_id"), nullable=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    withdrawn: Mapped[int] = mapped_column(Integer, default=0)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="user", foreign_keys="Purchase.user_id")
    withdrawals: Mapped[list["Withdrawal"]] = relationship("Withdrawal", back_populates="user")
    referrals_given: Mapped[list["Referral"]] = relationship("Referral", back_populates="referrer", foreign_keys="Referral.referrer_id")
    support_tickets: Mapped[list["SupportTicket"]] = relationship("SupportTicket", back_populates="user")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    media_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    channel_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="course")


class CourseBundle(Base):
    """
    Chegirma qoidasi: N ta kurs tanlansa — umumiy narx bundle_price bo'ladi.
    Agar mos bundle topilmasa — kurslar narxi oddiy qo'shiladi.
    """
    __tablename__ = "course_bundles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_count: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    bundle_price: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Purchase(Base):
    """Bitta yoki bir nechta kurs uchun bitta to'lov"""
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    # group_id: bir xil to'lovga tegishli kurslar bir xil group_id ga ega
    group_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    receipt_photo: Mapped[str | None] = mapped_column(String(256), nullable=True)
    amount_paid: Mapped[int] = mapped_column(Integer, default=0)
    original_price: Mapped[int] = mapped_column(Integer, default=0)
    reject_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    approved_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    invite_link_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="purchases", foreign_keys=[user_id])
    course: Mapped["Course"] = relationship("Course", back_populates="purchases")


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"), nullable=False, index=True)
    referral_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"), nullable=False, index=True)
    bonus_earned: Mapped[int] = mapped_column(Integer, default=0)
    is_bought: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    referrer: Mapped["User"] = relationship("User", back_populates="referrals_given", foreign_keys=[referrer_id])

    __table_args__ = (
        UniqueConstraint("referral_id", name="uq_referral_referral_id"),
    )


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"), nullable=False, index=True)
    card_number: Mapped[str] = mapped_column(String(32), nullable=False)
    card_holder: Mapped[str | None] = mapped_column(String(256), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="withdrawals")


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PaymentCard(Base):
    __tablename__ = "payment_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_number: Mapped[str] = mapped_column(String(32), nullable=False)
    holder_name: Mapped[str] = mapped_column(String(256), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(128), nullable=False)
    card_type: Mapped[str] = mapped_column(String(32), default="Uzcard")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"), nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped["User"] = relationship("User", back_populates="support_tickets")


class SponsorChannel(Base):
    __tablename__ = "sponsor_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    channel_name: Mapped[str] = mapped_column(String(256), nullable=False)
    channel_link: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BotSettings(Base):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
