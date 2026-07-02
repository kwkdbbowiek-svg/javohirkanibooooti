from aiogram import Router
from .start import router as start_router
from .courses import router as courses_router
from .purchase import router as purchase_router
from .my_courses import router as my_courses_router
from .referral import router as referral_router
from .subscription import router as subscription_router
from .support import router as support_router

router = Router(name="user")
router.include_router(start_router)
router.include_router(subscription_router)
router.include_router(courses_router)
router.include_router(purchase_router)
router.include_router(my_courses_router)
router.include_router(referral_router)
router.include_router(support_router)
