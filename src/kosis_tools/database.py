"""Database connection module for PostgreSQL (optional, for FTS-based metadata search).

Provides async connection pooling and helper functions for database operations.

Usage:
    # In application startup
    await DatabasePool.initialize()

    # Get connection from pool
    async with DatabasePool.connection() as conn:
        result = await conn.fetch("SELECT * FROM kosis_tables LIMIT 10")

    # Cleanup on shutdown
    await DatabasePool.close()
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator, Any

logger = logging.getLogger(__name__)

# Optional imports - gracefully handle missing asyncpg
try:
    import asyncpg
    from asyncpg import Pool, Connection

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    Pool = Any
    Connection = Any


class DatabaseError(Exception):
    """Database operation error."""

    pass


class DatabasePool:
    """Async PostgreSQL connection pool manager.

    Thread-safe singleton pattern for managing database connections.
    Uses asyncpg for high-performance async PostgreSQL access.
    """

    _pool: Optional[Pool] = None
    _initialized: bool = False

    @classmethod
    async def initialize(
        cls,
        database_url: Optional[str] = None,
        min_size: int = 2,
        max_size: int = 10,
    ) -> None:
        """Initialize the connection pool.

        Args:
            database_url: PostgreSQL connection URL. If None, reads from DATABASE_URL env.
            min_size: Minimum number of connections in pool.
            max_size: Maximum number of connections in pool.

        Raises:
            DatabaseError: If asyncpg is not installed or connection fails.
        """
        if cls._initialized:
            logger.debug("Database pool already initialized")
            return

        if not ASYNCPG_AVAILABLE:
            raise DatabaseError(
                "asyncpg is not installed. Install with: uv add asyncpg"
            )

        url = database_url or os.environ.get("DATABASE_URL")
        if not url:
            raise DatabaseError(
                "DATABASE_URL not provided and not found in environment"
            )

        # Convert SQLAlchemy-style URL to asyncpg format if needed
        # postgresql+asyncpg://... -> postgresql://...
        if "+asyncpg" in url:
            url = url.replace("+asyncpg", "")

        try:
            cls._pool = await asyncpg.create_pool(
                url,
                min_size=min_size,
                max_size=max_size,
                init=cls._init_connection,
            )
            cls._initialized = True
            logger.info(f"Database pool initialized (min={min_size}, max={max_size})")
        except Exception as e:
            raise DatabaseError(f"Failed to create database pool: {e}") from e

    @classmethod
    async def _init_connection(cls, conn: Connection) -> None:
        """Initialize each new database connection."""
        await conn.execute("SET search_path TO public")

    @classmethod
    async def close(cls) -> None:
        """Close the connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            cls._initialized = False
            logger.info("Database pool closed")

    @classmethod
    def get_pool(cls) -> Pool:
        """Get the connection pool.

        Raises:
            DatabaseError: If pool not initialized.
        """
        if not cls._initialized or cls._pool is None:
            raise DatabaseError(
                "Database pool not initialized. Call DatabasePool.initialize() first."
            )
        return cls._pool

    @classmethod
    @asynccontextmanager
    async def connection(cls) -> AsyncGenerator[Connection, None]:
        """Get a connection from the pool.

        Usage:
            async with DatabasePool.connection() as conn:
                result = await conn.fetch("SELECT ...")

        Yields:
            asyncpg.Connection: Database connection from pool.

        Raises:
            DatabaseError: If pool not initialized.
        """
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            yield conn

    @classmethod
    async def execute(cls, query: str, *args) -> str:
        """Execute a query and return status.

        Args:
            query: SQL query string.
            *args: Query parameters.

        Returns:
            Command status string (e.g., "INSERT 0 1")
        """
        async with cls.connection() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def fetch(cls, query: str, *args) -> list:
        """Execute a query and fetch all results.

        Args:
            query: SQL query string.
            *args: Query parameters.

        Returns:
            List of Record objects.
        """
        async with cls.connection() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def fetchrow(cls, query: str, *args) -> Optional[Any]:
        """Execute a query and fetch single row.

        Args:
            query: SQL query string.
            *args: Query parameters.

        Returns:
            Single Record object or None.
        """
        async with cls.connection() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetchval(cls, query: str, *args) -> Any:
        """Execute a query and fetch single value.

        Args:
            query: SQL query string.
            *args: Query parameters.

        Returns:
            Single value from first column of first row.
        """
        async with cls.connection() as conn:
            return await conn.fetchval(query, *args)


async def check_database_health() -> dict:
    """Check database connectivity and health.

    Returns:
        Dict with health status information.
    """
    try:
        if not DatabasePool._initialized:
            return {
                "status": "not_initialized",
                "message": "Database pool not initialized",
            }

        # Test query
        result = await DatabasePool.fetchrow(
            "SELECT NOW() as time, current_database() as db"
        )

        # Check table count
        count = await DatabasePool.fetchval("SELECT COUNT(*) FROM kosis_tables")

        return {
            "status": "healthy",
            "database": result["db"],
            "server_time": str(result["time"]),
            "table_count": count,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


# Convenience function for creating tables during development
async def ensure_schema() -> None:
    """Ensure database schema exists (for development).

    In production, use migrations/init.sql instead.
    """
    schema_check = await DatabasePool.fetchval(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'kosis_tables'
        )
        """
    )

    if not schema_check:
        logger.warning("kosis_tables not found - schema may need initialization")
        raise DatabaseError(
            "Database schema not initialized. "
            "Run: docker compose up postgres (with init.sql)"
        )

    logger.info("Database schema verified")
