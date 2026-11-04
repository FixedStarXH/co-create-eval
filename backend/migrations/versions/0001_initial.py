"""Create the versioned task table.

Revision ID: 0001_initial
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_version",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_code", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("scenario", sa.String(), nullable=False),
        sa.Column("instructions", sa.String(), nullable=False),
        sa.Column("constraints_json", sa.String(), nullable=False),
        sa.Column("ideation_seconds", sa.Integer(), nullable=False),
        sa.Column("development_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("task_code", "version", name="uq_task_code_version"),
        sa.CheckConstraint("ideation_seconds > 0 AND development_seconds > 0", name="ck_task_duration_positive"),
        sa.CheckConstraint("status IN ('DRAFT', 'PUBLISHED')", name="ck_task_status"),
    )


def downgrade():
    op.drop_table("task_version")
