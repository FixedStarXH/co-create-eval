"""Add participants, assigned sessions and login sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0002_participant"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("participant", sa.Column("id", sa.String(36), primary_key=True), sa.Column("study_code", sa.String(32), nullable=False, unique=True), sa.Column("credential_hash", sa.String(255), nullable=False), sa.Column("sequence", sa.String(2), nullable=False), sa.Column("consent_version", sa.String(32)), sa.Column("consented_at", sa.DateTime()), sa.CheckConstraint("sequence IN ('S1','S2','S3','S4')", name="ck_participant_sequence"))
    op.create_table("study_session", sa.Column("id", sa.String(36), primary_key=True), sa.Column("participant_id", sa.String(36), sa.ForeignKey("participant.id"), nullable=False), sa.Column("task_version_id", sa.String(36), sa.ForeignKey("task_version.id"), nullable=False), sa.Column("round_no", sa.Integer(), nullable=False), sa.Column("condition", sa.String(16), nullable=False), sa.Column("state", sa.String(16), nullable=False), sa.UniqueConstraint("participant_id", "round_no", name="uq_participant_round"), sa.CheckConstraint("round_no IN (1,2)", name="ck_session_round"), sa.CheckConstraint("condition IN ('AI','INDEPENDENT')", name="ck_session_condition"))
    op.create_index("ix_study_session_participant_id", "study_session", ["participant_id"])
    op.create_table("auth_session", sa.Column("id", sa.String(36), primary_key=True), sa.Column("participant_id", sa.String(36), sa.ForeignKey("participant.id"), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("csrf_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_auth_session_participant_id", "auth_session", ["participant_id"])

def downgrade():
    op.drop_index("ix_auth_session_participant_id", table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_index("ix_study_session_participant_id", table_name="study_session")
    op.drop_table("study_session")
    op.drop_table("participant")
