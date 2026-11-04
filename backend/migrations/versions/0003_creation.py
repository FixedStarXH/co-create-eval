"""Add timed creation stages, drafts and immutable snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0003_creation"
down_revision = "0002_participant"
branch_labels = None
depends_on = None

def upgrade():
    for name in ("ideation_started_at", "ideation_deadline_at", "idea_submitted_at", "development_started_at", "development_deadline_at", "submitted_at"):
        op.add_column("study_session", sa.Column(name, sa.DateTime(), nullable=True))
    for name in ("idea_draft", "artifact_draft"):
        op.create_table(name, sa.Column("session_id", sa.String(36), sa.ForeignKey("study_session.id"), primary_key=True), sa.Column("content_json", sa.String(), nullable=False), sa.Column("revision_no", sa.Integer(), nullable=False), sa.Column("saved_at", sa.DateTime(), nullable=True))
    op.create_table("artifact_version", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("study_session.id"), nullable=False), sa.Column("stage", sa.String(16), nullable=False), sa.Column("revision_no", sa.Integer(), nullable=False), sa.Column("content_json", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("session_id", "stage", name="uq_session_version_stage"), sa.CheckConstraint("stage IN ('INITIAL','FINAL')", name="ck_version_stage"))
    op.create_index("ix_artifact_version_session_id", "artifact_version", ["session_id"])

def downgrade():
    op.drop_index("ix_artifact_version_session_id", table_name="artifact_version")
    op.drop_table("artifact_version")
    op.drop_table("artifact_draft")
    op.drop_table("idea_draft")
    for name in ("submitted_at", "development_deadline_at", "development_started_at", "idea_submitted_at", "ideation_deadline_at", "ideation_started_at"):
        op.drop_column("study_session", name)
