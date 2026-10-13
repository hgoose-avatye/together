"""이메일 소유 확인 (기획서 5.10, 7.3, 안전 묶음 PR 3)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 비어 있으면 미인증. 이미 있는 계정도 미인증으로 시작한다(운영자가 admin.py verify-email로 인증).
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),  # SHA-256 hex. 원문은 저장하지 않는다
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_email_verification_tokens"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_email_verification_tokens_user_id_users"
        ),
        sa.UniqueConstraint("token_hash", name="uq_email_verification_tokens_token_hash"),
        sa.CheckConstraint(
            "length(token_hash) = 64", name=op.f("ck_email_verification_tokens_token_hash_len")
        ),
    )
    op.create_index(
        "ix_email_verification_tokens_user_id_created_at",
        "email_verification_tokens",
        ["user_id", "created_at"],
    )
    op.execute("ALTER TABLE email_verification_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verified_at")
