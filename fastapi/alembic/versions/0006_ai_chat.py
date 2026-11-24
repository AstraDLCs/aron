"""Conversaciones de IA.

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

CLOCK = sa.text("clock_timestamp()")


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("created_by_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.Column("structured_report", JSONB, nullable=True),
    )
    op.create_index("ix_ai_conversations_candidate_id", "ai_conversations", ["candidate_id"])
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.Column("vote", sa.String(4), nullable=True),
        sa.Column("feedback_note", sa.Text, nullable=False, server_default=""),
        sa.CheckConstraint("role in ('assistant','user')", name="ck_ai_messages_role"),
        sa.CheckConstraint("vote is null or vote in ('up','down')", name="ck_ai_messages_vote"),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
