import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, SUPER_ADMIN_IDS
from database.engine import engine, async_session, Base
from database.crud import get_user, set_user_role
from handlers.user import router as user_router
from handlers.admin import router as admin_router
from middlewares.auth import AuthMiddleware
from middlewares.subscription import SubscriptionMiddleware
from tasks.scheduler import setup_scheduler

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("\u2705 Jadvallar tekshirildi / yaratildi.")


async def ensure_super_admins():
    async with async_session() as session:
        for admin_id in SUPER_ADMIN_IDS:
            user = await get_user(session, admin_id)
            if user and user.role != "superadmin":
                await set_user_role(session, admin_id, "superadmin")
                logger.info(f"\u2705 Super admin roli berildi: {admin_id}")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Routerlar (admin birinchi - yuqori prioritet)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    return dp


async def on_startup(bot: Bot, dp: Dispatcher):
    """Bot ishga tushganda bajariladi"""
    await create_tables()
    await ensure_super_admins()

    # Polling rejimi: eski webhookni o'chirish
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("\u2705 Polling rejimi ? webhook o'chirildi.")

    bot_info = await bot.get_me()
    logger.info(f"\u2705 Bot: @{bot_info.username} (ID: {bot_info.id})")
    logger.info(f"\u2705 Super adminlar: {SUPER_ADMIN_IDS}")


async def on_shutdown(bot: Bot):
    """Bot to'xtatilganda bajariladi"""
    await bot.session.close()
    logger.info("Bot to'xtatildi.")


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN .env faylida topilmadi!")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = build_dispatcher()

    # Scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("\u2705 Scheduler ishga tushdi.")

    logger.info("\U0001F680 Polling rejimida ishga tushmoqda...")

    await on_startup(bot, dp)

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
    finally:
        scheduler.shutdown()
        await on_shutdown(bot)


if __name__ == "__main__":
    asyncio.run(main())
