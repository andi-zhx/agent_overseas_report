"""FastAPI routers for the overseas-report backend."""

from .enterprises import router as enterprise_master_data_router
from .health import router as health_router
from .knowledge_files import router as knowledge_files_router
from .overseas_plans import router as overseas_plans_router

__all__ = ["enterprise_master_data_router", "health_router", "knowledge_files_router", "overseas_plans_router"]
