"""Database connection shared by the API and migrations."""

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlmodel import create_engine


def build_engine(url: str):
    parsed = make_url(url)
    options = {}
    if parsed.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **options)
    if parsed.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine
