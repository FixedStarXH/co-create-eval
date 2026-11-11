"""Persist creation chat requests and outcomes."""
from alembic import op
import sqlalchemy as sa

revision = "0004_chat"
down_revision = "0003_creation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("study_session.id"), nullable=False),
        sa.Column("client_request_id", sa.String(36), nullable=False),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("reply", sa.String(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("provider_request_id", sa.String(200), nullable=True),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("session_id", "client_request_id", name="uq_chat_client_request"),
        sa.CheckConstraint("status IN ('PENDING','SUCCEEDED','FAILED')", name="ck_chat_status"),
    )
    op.create_index("ix_chat_request_session_id", "chat_request", ["session_id"])


def downgrade():
    op.drop_index("ix_chat_request_session_id", table_name="chat_request")
    op.drop_table("chat_request")
