"""HTTP entry point. Domain endpoints will be added with authorization."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import database_url
from app.db import build_engine
from app.participant_api import router as participant_router
from app.creation_api import router as creation_router

EXPECTED_REVISION = "0003_creation"


def create_app(url: str | None = None) -> FastAPI:
    engine = build_engine(url or database_url())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(title="Co-create Eval API", version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.include_router(participant_router)
    app.include_router(creation_router)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/ready")
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                tables = inspect(connection)
                if not tables.has_table("alembic_version") or not tables.has_table("task_version"):
                    return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "migration_required"})
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
                if revision != EXPECTED_REVISION:
                    return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "migration_required"})
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "database_unavailable"})
        return {"status": "ready", "database": "ok", "revision": revision}

    return app


app = create_app()
