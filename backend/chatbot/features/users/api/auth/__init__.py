from ninja import Router

from .signup import router as signup_router
from .token import router as token_router

router = Router()
router.add_router('', token_router)
router.add_router('', signup_router)
