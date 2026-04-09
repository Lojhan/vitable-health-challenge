from ninja import NinjaAPI

from .auth import router as auth_router

api = NinjaAPI()
api.add_router('/auth', auth_router, tags=['Authentication'])
