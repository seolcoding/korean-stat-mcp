"""FastMCP Streamable HTTP application for production deployment.

This module provides an ASGI application for running the KOSIS MCP server
with a Streamable HTTP MCP endpoint at /mcp, suitable for production deployment
with uvicorn. The app itself serves plain HTTP on port 8000; deployment
platforms or reverse proxies terminate HTTPS externally.

Usage:
    # Development
    uvicorn mcp_server.app:app --reload

    # Production
    uvicorn mcp_server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # With environment variable
    FASTMCP_STATELESS_HTTP=true uvicorn mcp_server.app:app
"""

import logging
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.requests import Request

logger = logging.getLogger(__name__)

_CUSTOM_ROUTES_REGISTERED = False


def _package_version() -> str:
    """Return the installed package version for deployment metadata."""
    try:
        return version("korean-stat-mcp")
    except PackageNotFoundError:
        return "0.1.0"


def create_app() -> Starlette:
    """Create the ASGI app exposed by local HTTP and remote deployments."""
    global _CUSTOM_ROUTES_REGISTERED

    from .server import mcp

    # Check if stateless HTTP mode is enabled
    stateless = os.environ.get("FASTMCP_STATELESS_HTTP", "").lower() in (
        "true",
        "1",
        "yes",
    )

    # Initialize database pool at module load time (not just on startup event)
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        import asyncio
        from kosis_tools.database import DatabasePool

        async def _init_db():
            try:
                await DatabasePool.initialize(database_url)
                logger.info(
                    f"Database pool initialized: {database_url.split('@')[1] if '@' in database_url else 'configured'}"
                )
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

    if not _CUSTOM_ROUTES_REGISTERED:
        # Add custom routes to the MCP server (avoid "/" to not interfere with MCP)
        @mcp.custom_route("/info", methods=["GET"])
        async def info_handler(request: Request) -> JSONResponse:
            return JSONResponse(
                {
                    "service": "korean-stat-mcp",
                    "version": _package_version(),
                    "description": "MCP server for Korean Statistical Data",
                    "endpoints": {
                        "health": "/health",
                        "info": "/info",
                        "mcp": "/mcp",
                        "artifacts": "/artifacts",
                    },
                    "protocol": "MCP Streamable HTTP",
                }
            )

        @mcp.custom_route("/health", methods=["GET"])
        async def health_handler(request: Request) -> JSONResponse:
            status = {"status": "healthy", "service": "korean-stat-mcp"}
            try:
                from kosis_tools.database import check_database_health

                db_health = await check_database_health()
                status["database"] = db_health
            except Exception as e:
                status["database"] = {"status": "unavailable", "error": str(e)}
            return JSONResponse(status)

        _CUSTOM_ROUTES_REGISTERED = True

    # Create MCP app with the public Streamable HTTP endpoint at /mcp. JSON
    # responses are an HTTP transport choice; stdio mode keeps FastMCP defaults.
    mcp_app = mcp.http_app(
        path="/mcp",
        json_response=True,
        stateless_http=stateless,
    )

    # Add static files route for artifacts
    mcp_app.routes.append(
        Mount(
            "/artifacts",
            app=StaticFiles(directory=str(artifacts_path)),
            name="artifacts",
        )
    )

    # Add CORS middleware
    mcp_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Per-request KOSIS API key extraction. Must run before MCP handlers so
    # that load_config() inside any tool sees the request's key.
    from .middleware import ApiKeyMiddleware
    mcp_app.add_middleware(ApiKeyMiddleware)

    # Rate limiting (default 300 rpm, override via RATE_LIMIT_RPM).
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    from .middleware import build_rate_limiter

    limiter = build_rate_limiter()
    mcp_app.state.limiter = limiter
    mcp_app.add_middleware(SlowAPIMiddleware)

    # slowapi's _get_route_name() calls handler.__name__, but FastMCP mounts
    # StreamableHTTPASGIApp (an ASGI object, not a plain function).  Patch
    # __name__ / __module__ so slowapi can build a route name, then exempt
    # /mcp entirely — authentication there is already handled by ApiKeyMiddleware.
    for route in mcp_app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None and not hasattr(endpoint, "__name__"):
            endpoint.__name__ = "mcp_asgi_app"
            endpoint.__module__ = "fastmcp.server.http"
            limiter._exempt_routes.add(
                f"{endpoint.__module__}.{endpoint.__name__}"
            )

    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            {"error": "rate_limit_exceeded", "detail": str(exc.detail)},
            status_code=429,
            headers={"Retry-After": "60"},
        )

    mcp_app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    # Add startup event for DB initialization
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
