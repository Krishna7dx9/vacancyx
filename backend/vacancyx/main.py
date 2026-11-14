"""FastAPI application entry point."""

from fastapi import FastAPI

from vacancyx import __version__
from vacancyx.config import get_settings


def create_app() -> FastAPI:
    """Application factory keeps app construction deterministic in tests."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Local-first job discovery and application workflow platform.",
    )

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        """Report that the API process can serve requests; no dependency checks here."""
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, str]:
        """Initial readiness probe. Dependency checks are added with persistence."""
        return {"status": "ready"}

    return app


app = create_app()
