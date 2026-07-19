from contextlib import asynccontextmanager
from fastapi import FastAPI
from .seeding_utils import seed_database_at_startup
from .utils.audit_logger import set_audit_loop
from .database import engine
from .routers.api import sis as sis_router
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run seeding logic
    # Capture the main event loop for background audit threads
    set_audit_loop(asyncio.get_running_loop())
    
    print("[*] Running startup lifecycle tasks...")
    sis_router.ensure_sis_api_key_table(engine)
    seed_database_at_startup()
    yield
    # Shutdown: Clean up or log if needed
    print("[*] Running shutdown lifecycle tasks...")
