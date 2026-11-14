"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from vacancyx import __version__
from vacancyx.api.router import api_router
from vacancyx.config import get_settings
from vacancyx.db.session import check_database_connection


def create_app() -> FastAPI:
    """Application factory keeps app construction deterministic in tests."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Local-first job discovery and application workflow platform.",
    )
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        """Report that the API process can serve requests; no dependency checks here."""
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"], response_model=None)
    async def readiness() -> dict[str, str] | JSONResponse:
        """Report readiness only when the configured database accepts a connection."""
        try:
            check_database_connection()
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    return app


app = create_app()
