from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.v1.router import router
from .config import settings
from .container import container


@asynccontextmanager
async def lifespan(_: FastAPI):
    # SQLite и репозитории поднимаем до первого запроса. На shutdown аккуратно
    # закрываем executor, чтобы docker stop не оставлял недописанные job states.
    current = container()
    try:
        yield
    finally:
        current.job_manager.shutdown()


cfg = settings()
app = FastAPI(
    title="FloraScope API",
    version=__version__,
    description="Восстановление NDVI и мониторинг аномальной вегетации",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
