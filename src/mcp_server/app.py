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


def create_app() -> Starlette:
    """Create the application with MCP server as main app.

    FastMCP's http_app() is the main app, with custom routes added via
    custom_route decorator or as additional routes.
    """
    from .server import mcp

    # Check if stateless HTTP mode is enabled
    stateless = os.environ.get("FASTMCP_STATELESS_HTTP", "").lower() in (
        "true", "1", "yes"
    )

    # Initialize database pool at module load time (not just on startup event)
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        import asyncio
        from kosis_tools.database import DatabasePool

        async def _init_db():
            try:
                await DatabasePool.initialize(database_url)
                logger.info(f"Database pool initialized: {database_url.split('@')[1] if '@' in database_url else 'configured'}")
            except Exception as e:
                logger.warning(f"Database initialization failed: {e}")

        # Run in event loop if available, otherwise create new one
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_init_db())
        except RuntimeError:
            asyncio.run(_init_db())

    if stateless:
        logger.info("Creating MCP server in stateless HTTP mode")
    else:
        logger.info("Creating MCP server in standard mode")

    # Setup artifacts directory
    artifacts_dir = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
    artifacts_path = Path(artifacts_dir)
    for subdir in ["charts", "reports", "data"]:
        (artifacts_path / subdir).mkdir(parents=True, exist_ok=True)
    logger.info(f"Static files mounted at /artifacts -> {artifacts_path}")

    # Add custom routes to the MCP server (avoid "/" to not interfere with MCP)
    @mcp.custom_route("/info", methods=["GET"])
    async def info_handler(request: Request) -> JSONResponse:
        return JSONResponse({
            "service": "KOSIS MCP Server",
            "version": "0.2.0",
            "description": "MCP server for Korean Statistical Data",
            "endpoints": {
                "health": "/health",
                "info": "/info",
                "mcp": "/ (MCP Streamable HTTP protocol - POST)",
            },
        })

    @mcp.custom_route("/health", methods=["GET"])
    async def health_handler(request: Request) -> JSONResponse:
        status = {"status": "healthy", "service": "kosis-mcp"}
        try:
            from kosis_tools.database import check_database_health
            db_health = await check_database_health()
            status["database"] = db_health
        except Exception as e:
            status["database"] = {"status": "unavailable", "error": str(e)}
        return JSONResponse(status)

    # Create MCP app as main app with explicit root path
    mcp_app = mcp.http_app(path="/", stateless_http=stateless)

    # Add static files route for artifacts
    mcp_app.routes.append(
        Mount("/artifacts", app=StaticFiles(directory=str(artifacts_path)), name="artifacts")
    )

    # Add CORS middleware
    mcp_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add startup event for DB initialization
    original_startup = mcp_app.on_startup if hasattr(mcp_app, 'on_startup') else []

    async def init_database():
        logger.info("KOSIS MCP Server starting up...")
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            try:
                from kosis_tools.database import DatabasePool
                await DatabasePool.initialize(database_url)
                logger.info("Database pool initialized")
            except Exception as e:
                logger.warning(f"Database initialization failed: {e}")

    async def close_database():
        logger.info("KOSIS MCP Server shutting down...")
        try:
            from kosis_tools.database import DatabasePool
            await DatabasePool.close()
        except Exception:
            pass

    mcp_app.add_event_handler("startup", init_database)
    mcp_app.add_event_handler("shutdown", close_database)

    return mcp_app


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
