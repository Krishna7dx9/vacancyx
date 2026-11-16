import os
import stat

from sqlalchemy import text

from vacancyx.db.session import build_engine, check_database_connection


def test_sqlite_engine_creates_parent_and_enables_foreign_keys(tmp_path) -> None:
    database_path = tmp_path / "nested" / "vacancyx.sqlite3"
    engine = build_engine(f"sqlite:///{database_path}")
    try:
        assert database_path.parent.is_dir()
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert check_database_connection(engine)
    finally:
        engine.dispose()


def test_file_backed_database_is_owner_read_write_only_on_posix(tmp_path) -> None:
    if os.name != "posix":
        return
    database_path = tmp_path / "private" / "vacancyx.sqlite3"
    engine = build_engine(f"sqlite:///{database_path}")
    try:
        assert check_database_connection(engine)
        assert stat.S_IMODE(database_path.stat().st_mode) == 0o600
    finally:
        engine.dispose()
