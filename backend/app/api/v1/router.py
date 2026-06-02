from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    admin,
    auth,
    dev_platform,
    health,
    modules,
    overlaps,
    projects,
)
from app.api.v1 import platform as platform_routes
from app.store import store


def sync_platform_store() -> None:
    store.reload_if_changed()


api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
# POC platform store routes must register before SQL /modules to own shared paths.
api_router.include_router(
    platform_routes.router,
    dependencies=[Depends(sync_platform_store)],
)
api_router.include_router(
    dev_platform.router,
    dependencies=[Depends(sync_platform_store)],
)
api_router.include_router(
    overlaps.router,
    dependencies=[Depends(sync_platform_store)],
)
api_router.include_router(modules.router, prefix="/modules", tags=["Modules"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
