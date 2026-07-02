from aiogram import Router
from .stats import router as stats_router
from .purchases import router as purchases_router
from .courses import router as courses_router
from .cards import router as cards_router
from .bundles import router as bundles_router
from .withdrawals import router as withdrawals_router
from .broadcast import router as broadcast_router
from .admins import router as admins_router
from .sponsors import router as sponsors_router
from .settings import router as settings_router
from .users import router as users_router

router = Router(name="admin")
router.include_router(stats_router)
router.include_router(purchases_router)
router.include_router(withdrawals_router)
router.include_router(courses_router)
router.include_router(cards_router)
router.include_router(bundles_router)
router.include_router(broadcast_router)
router.include_router(admins_router)
router.include_router(sponsors_router)
router.include_router(settings_router)
router.include_router(users_router)
