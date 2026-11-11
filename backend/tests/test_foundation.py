from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.main import create_app
from app.models import TaskVersion

ROOT = Path(__file__).resolve().parents[1]


def migrate(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")


def test_readiness_requires_migration_and_persists_task(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}"
    app = create_app(url)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.get("/api/v1/ready").status_code == 503
        migrate(monkeypatch, url)
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        assert response.json()["revision"] == "0004_chat"
        with Session(app.state.engine) as session:
            session.add(TaskVersion(task_code="A", version="1", title="任务 A", scenario="情境", instructions="要求"))
            session.commit()
        with Session(app.state.engine) as session:
            assert session.exec(select(TaskVersion)).one().title == "任务 A"


def test_task_version_constraints(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'constraints.sqlite3').as_posix()}"
    migrate(monkeypatch, url)
    app = create_app(url)
    with Session(app.state.engine) as session:
        session.add(TaskVersion(task_code="A", version="1", title="A", scenario="S", instructions="I"))
        session.commit()
        session.add(TaskVersion(task_code="A", version="1", title="duplicate", scenario="S", instructions="I"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(TaskVersion(task_code="B", version="1", title="B", scenario="S", instructions="I", ideation_seconds=0))
        with pytest.raises(IntegrityError):
            session.commit()
    app.state.engine.dispose()
