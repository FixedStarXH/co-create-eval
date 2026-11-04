"""Versioned task configuration; referenced versions must remain traceable."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel


class TaskVersion(SQLModel, table=True):
    __tablename__ = "task_version"
    __table_args__ = (
        UniqueConstraint("task_code", "version", name="uq_task_code_version"),
        CheckConstraint("ideation_seconds > 0 AND development_seconds > 0", name="ck_task_duration_positive"),
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED')", name="ck_task_status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    task_code: str = Field(max_length=32, nullable=False)
    version: str = Field(max_length=32, nullable=False)
    title: str = Field(max_length=200, nullable=False)
    scenario: str = Field(nullable=False)
    instructions: str = Field(nullable=False)
    constraints_json: str = Field(default="[]", nullable=False)
    ideation_seconds: int = Field(default=300, nullable=False)
    development_seconds: int = Field(default=1200, nullable=False)
    status: str = Field(default="DRAFT", max_length=16, nullable=False)
    published_at: datetime | None = Field(default=None)
