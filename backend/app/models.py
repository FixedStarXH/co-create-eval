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


class Participant(SQLModel, table=True):
    __tablename__ = "participant"
    __table_args__ = (CheckConstraint("sequence IN ('S1','S2','S3','S4')", name="ck_participant_sequence"),)
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    study_code: str = Field(max_length=32, nullable=False, unique=True)
    credential_hash: str = Field(max_length=255, nullable=False)
    sequence: str = Field(max_length=2, nullable=False)
    consent_version: str | None = Field(default=None, max_length=32)
    consented_at: datetime | None = Field(default=None)


class StudySession(SQLModel, table=True):
    __tablename__ = "study_session"
    __table_args__ = (
        UniqueConstraint("participant_id", "round_no", name="uq_participant_round"),
        CheckConstraint("round_no IN (1,2)", name="ck_session_round"),
        CheckConstraint("condition IN ('AI','INDEPENDENT')", name="ck_session_condition"),
    )
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    participant_id: str = Field(foreign_key="participant.id", nullable=False, max_length=36, index=True)
    task_version_id: str = Field(foreign_key="task_version.id", nullable=False, max_length=36)
    round_no: int = Field(nullable=False)
    condition: str = Field(max_length=16, nullable=False)
    state: str = Field(default="CREATED", max_length=16, nullable=False)


class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_session"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    participant_id: str = Field(foreign_key="participant.id", nullable=False, max_length=36, index=True)
    token_hash: str = Field(max_length=64, nullable=False, unique=True)
    csrf_hash: str = Field(max_length=64, nullable=False)
    expires_at: datetime = Field(nullable=False)
