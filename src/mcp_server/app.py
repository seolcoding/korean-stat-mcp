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
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.requests import Request

logger = logging.getLogger(__name__)


async def health_check(request: Request) -> JSONResponse:
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


async def root(request: Request) -> JSONResponse:
    """Root endpoint with API info."""
    return JSONResponse({
        "service": "KOSIS MCP Server",
        "version": "0.2.0",
        "description": "MCP server for Korean Statistical Data",
        "endpoints": {
            "health": "/health",
            "mcp": "/mcp (MCP Streamable HTTP protocol)",
        },
    })


def create_app() -> Starlette:
    """Create the Starlette application with MCP server.

    Returns:
        Starlette application instance.
    """
    from .server import mcp

    # Check if stateless HTTP mode is enabled
    stateless = os.environ.get("FASTMCP_STATELESS_HTTP", "").lower() in (
        "true", "1", "yes"
    )

    if stateless:
        logger.info("Creating MCP server in stateless HTTP mode")
    else:
        logger.info("Creating MCP server in standard mode")

    # Create MCP app (mounted at /mcp, so internal path is "/")
    mcp_app = mcp.http_app(stateless_http=stateless)

    # Setup artifacts directory
    artifacts_dir = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
    artifacts_path = Path(artifacts_dir)
    for subdir in ["charts", "reports", "data"]:
        (artifacts_path / subdir).mkdir(parents=True, exist_ok=True)
    logger.info(f"Static files mounted at /artifacts -> {artifacts_path}")

    # Create custom lifespan that initializes DB
    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator:
        # Startup
        logger.info("KOSIS MCP Server starting up...")

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

    # Build routes - MCP at /mcp, custom routes at root
    routes = [
        Route("/", root),
        Route("/health", health_check),
        Mount("/artifacts", app=StaticFiles(directory=str(artifacts_path)), name="artifacts"),
        Mount("/mcp", app=mcp_app),
    ]

    # CORS middleware
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]

    # Create Starlette app with MCP lifespan
    app = Starlette(
        routes=routes,
        middleware=middleware,
        lifespan=lifespan,
    )

    return app


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
