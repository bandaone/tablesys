"""
Database configuration with optimized connection pooling.

Features:
- Environment-based pool sizing (dev: 5, prod: 10)
- Connection health checks (pool_pre_ping)
- Automatic connection recycling (prevents stale connections)
- Pool monitoring in development mode
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from .config import settings
import logging

logger = logging.getLogger(__name__)

# Environment-based pool configuration
if settings.ENVIRONMENT == "development":
    pool_config = {
        "pool_size": 5,        # Smaller pool for dev (saves resources)
        "max_overflow": 5,     # Less overflow needed
        "pool_recycle": 1800,  # 30 min recycle
    }
else:
    pool_config = {
        "pool_size": 10,       # Production settings
        "max_overflow": 20,    # Handle traffic bursts
        "pool_recycle": 3600,  # 1 hour recycle
    }

# Create engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,           # Queue-based connection pool
    pool_pre_ping=True,            # Verify connections before use (prevents stale connection errors)
    echo=settings.ENVIRONMENT == "development",  # SQL query logging in dev only
    connect_args={
        "connect_timeout": 10,     # 10 second connection timeout
        "options": "-c timezone=utc"  # Set timezone to UTC
    },
    **pool_config  # Apply environment-specific settings
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def setup_tenant_isolation():
    from .middleware.tenant import apply_orm_tenant_isolation
    apply_orm_tenant_isolation(SessionLocal)

def get_db():
    """
    Database session dependency for FastAPI.
    
    Yields a database session from the connection pool.
    Automatically returns the connection to the pool after use.
    
    In development mode, logs pool statistics for monitoring.
    """
    db = SessionLocal()
    try:
        # Log pool stats in development for monitoring
        if settings.ENVIRONMENT == "development":
            pool = engine.pool
            logger.debug(
                f"DB Pool: {pool.checkedin()}/{pool.size()} in, "
                f"{pool.checkedout()} out, {pool.overflow()} overflow"
            )
        yield db
    finally:
        db.close()
