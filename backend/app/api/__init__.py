from fastapi import APIRouter
from .routes.review import router as review_router
from .routes.health import router as health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(review_router)
