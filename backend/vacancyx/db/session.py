"""Engine and session construction with safe SQLite defaults."""

from collections.abc import Iterator
from functools import lru_cache
import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.config import get_settings


def build_engine(database_url: str) -> Engine:
    """Build an engine; create local database directories but never create schema implicitly."""
    url = make_url(database_url)
    connect_args: dict[str, object] = {}
    engine_options: dict[str, object] = {"pool_pre_ping": True}
    database_path: Path | None = None

    if url.get_backend_name() == "sqlite":
        database = url.database
        if database and database != ":memory:":
            database_path = Path(database).expanduser().resolve()
            database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
        if database in {None, ":memory:"}:
            engine_options["poolclass"] = StaticPool
        engine = create_engine(database_url, connect_args=connect_args, **engine_options)

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
            # SQLite's default creation mode follows the process umask (often 0644).
            # Candidate profiles and application history are private local data.
            if os.name == "posix" and database_path is not None and database_path.exists():
                database_path.chmod(0o600)

        return engine

    return create_engine(database_url, **engine_options)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process engine, cached for the application lifetime."""
    return build_engine(get_settings().database_url)


def get_session_factory() -> sessionmaker[Session]:
    """Return a session factory bound to the configured engine."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Yield a request-scoped session and always close it."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection(engine: Engine | None = None) -> bool:
    """Check connectivity without mutating schema or application data."""
    target = engine or get_engine()
    with target.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
