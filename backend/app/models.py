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
    ideation_started_at: datetime | None = Field(default=None)
    ideation_deadline_at: datetime | None = Field(default=None)
    idea_submitted_at: datetime | None = Field(default=None)
    development_started_at: datetime | None = Field(default=None)
    development_deadline_at: datetime | None = Field(default=None)
    submitted_at: datetime | None = Field(default=None)


class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_session"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    participant_id: str = Field(foreign_key="participant.id", nullable=False, max_length=36, index=True)
    token_hash: str = Field(max_length=64, nullable=False, unique=True)
    csrf_hash: str = Field(max_length=64, nullable=False)
    expires_at: datetime = Field(nullable=False)


class IdeaDraft(SQLModel, table=True):
    __tablename__ = "idea_draft"
    session_id: str = Field(foreign_key="study_session.id", primary_key=True, max_length=36)
    content_json: str = Field(default='["", "", ""]', nullable=False)
    revision_no: int = Field(default=0, nullable=False)
    saved_at: datetime | None = Field(default=None)


class ArtifactDraft(SQLModel, table=True):
    __tablename__ = "artifact_draft"
    session_id: str = Field(foreign_key="study_session.id", primary_key=True, max_length=36)
    content_json: str = Field(default="{}", nullable=False)
    revision_no: int = Field(default=0, nullable=False)
    saved_at: datetime | None = Field(default=None)


class ArtifactVersion(SQLModel, table=True):
    __tablename__ = "artifact_version"
    __table_args__ = (UniqueConstraint("session_id", "stage", name="uq_session_version_stage"), CheckConstraint("stage IN ('INITIAL','FINAL')", name="ck_version_stage"))
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    session_id: str = Field(foreign_key="study_session.id", nullable=False, max_length=36, index=True)
    stage: str = Field(nullable=False, max_length=16)
    revision_no: int = Field(nullable=False)
    content_json: str = Field(nullable=False)
    created_at: datetime = Field(nullable=False)


class ChatRequest(SQLModel, table=True):
    __tablename__ = "chat_request"
    __table_args__ = (
        UniqueConstraint("session_id", "client_request_id", name="uq_chat_client_request"),
        CheckConstraint("status IN ('PENDING','SUCCEEDED','FAILED')", name="ck_chat_status"),
    )
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    session_id: str = Field(foreign_key="study_session.id", nullable=False, max_length=36, index=True)
    client_request_id: str = Field(nullable=False, max_length=36)
    question: str = Field(nullable=False)
    reply: str | None = Field(default=None)
    status: str = Field(default="PENDING", nullable=False, max_length=16)
    model: str = Field(nullable=False, max_length=200)
    prompt_version: str = Field(nullable=False, max_length=32)
    provider_request_id: str | None = Field(default=None, max_length=200)
    error_code: str | None = Field(default=None, max_length=40)
    created_at: datetime = Field(nullable=False)
    completed_at: datetime | None = Field(default=None)
