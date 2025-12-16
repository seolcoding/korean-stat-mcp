"""FastMCP HTTP Application for Production Deployment.

This module provides an ASGI application for running the KOSIS MCP server
in HTTP mode (stateless), suitable for production deployment with uvicorn.

Usage:
    # Development
    uvicorn mcp_server.app:app --reload

    # Production
    uvicorn mcp_server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # With environment variable
    FASTMCP_STATELESS_HTTP=true uvicorn mcp_server.app:app
"""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("KOSIS MCP Server starting up...")

    # Initialize database pool if DATABASE_URL is set
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        try:
            from kosis_tools.database import DatabasePool
            await DatabasePool.initialize(database_url)
            logger.info("Database pool initialized")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
            logger.warning("Hybrid search will not be available")

    yield

    # Shutdown
    logger.info("KOSIS MCP Server shutting down...")
    try:
        from kosis_tools.database import DatabasePool
        await DatabasePool.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create the FastAPI application with MCP server mounted.

    Returns:
        FastAPI application instance.
    """
    # Create FastAPI app
    api = FastAPI(
        title="KOSIS MCP Server",
        description="MCP server for Korean Statistical Data (KOSIS) API",
        version="0.2.0",
        lifespan=lifespan,
    )

    # CORS middleware
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @api.get("/health")
    async def health_check():
        """Health check endpoint for container orchestration."""
        status = {"status": "healthy", "service": "kosis-mcp"}

        # Check database if available
        try:
            from kosis_tools.database import check_database_health
            db_health = await check_database_health()
            status["database"] = db_health
        except Exception as e:
            status["database"] = {"status": "unavailable", "error": str(e)}

        return JSONResponse(status)

    @api.get("/")
    async def root():
        """Root endpoint with API info."""
        return {
            "service": "KOSIS MCP Server",
            "version": "0.2.0",
            "description": "MCP server for Korean Statistical Data",
            "endpoints": {
                "health": "/health",
                "mcp": "/mcp (MCP protocol)",
            },
        }

    # Mount static files for artifacts
    artifacts_dir = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
    artifacts_path = Path(artifacts_dir)

    # Create artifact directories if they don't exist
    for subdir in ["charts", "reports", "data"]:
        (artifacts_path / subdir).mkdir(parents=True, exist_ok=True)

    # Mount static files
    api.mount(
        "/artifacts",
        StaticFiles(directory=str(artifacts_path)),
        name="artifacts"
    )
    logger.info(f"Static files mounted at /artifacts -> {artifacts_path}")

    # Mount MCP server
    try:
        from .server import mcp

        # Check if stateless HTTP mode is enabled
        stateless = os.environ.get("FASTMCP_STATELESS_HTTP", "").lower() in (
            "true", "1", "yes"
        )

        if stateless:
            logger.info("Mounting MCP server in stateless HTTP mode")
        else:
            logger.info("Mounting MCP server in standard mode")

        # Mount MCP app - use stateless_http parameter
        mcp_app = mcp.http_app(stateless_http=stateless)
        api.mount("/mcp", mcp_app)

    except Exception as e:
        logger.error(f"Failed to mount MCP server: {e}")
        raise

    return api


# Create application instance
app = create_app()


# For direct execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mcp_server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
