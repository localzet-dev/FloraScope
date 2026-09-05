from fastapi import APIRouter

from .analyses import router as analyses_router
from .benchmark import router as benchmark_router
from .fields import router as fields_router
from .jobs import router as jobs_router
from .system import router as system_router

router = APIRouter(prefix="/api/v1")
router.include_router(system_router)
router.include_router(fields_router)
router.include_router(jobs_router)
router.include_router(analyses_router)
router.include_router(benchmark_router)
