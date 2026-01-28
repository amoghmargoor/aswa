from fastapi import APIRouter

from .health import router as health_router
from .query import router as query_router
from .search import router as search_router
from .insights import router as insights_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(query_router, prefix="/query", tags=["query"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(insights_router, prefix="/insights", tags=["insights"])
