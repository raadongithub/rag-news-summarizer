"""Add normalized chat tables (3NF): chat_messages, message_critiques, message_passages."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260524_000002"
down_revision = "20260524_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create normalized chat tables.

    Returns
    -------
    None
        Tables are created in place.
    """

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"], unique=False)

    op.create_table(
        "message_critiques",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("is_faithful", sa.Boolean(), nullable=False),
        sa.Column("faithfulness_explanation", sa.Text(), nullable=False),
        sa.Column("is_relevant", sa.Boolean(), nullable=False),
        sa.Column("relevance_explanation", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )

    op.create_table(
        "message_passages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("base_similarity_score", sa.Float(), nullable=True),
        sa.Column("chunk_id", sa.String(length=128), nullable=True),
        sa.Column("article_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_message_passages_message_id"), "message_passages", ["message_id"], unique=False)


def downgrade() -> None:
    """Drop normalized chat tables.

    Returns
    -------
    None
        Tables are removed in reverse order.
    """

    op.drop_index(op.f("ix_message_passages_message_id"), table_name="message_passages")
    op.drop_table("message_passages")
    op.drop_table("message_critiques")
    op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
